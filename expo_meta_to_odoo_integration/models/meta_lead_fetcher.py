from odoo import models, fields, api,_
import requests
import json
from odoo.exceptions import UserError
from datetime import datetime, timedelta
from time import time
import logging
_logger = logging.getLogger(__name__)

class MetaLeadFetcher(models.Model):
    _name = 'meta.lead.fetcher'
    _description = "Meta Lead Fetcher"


    @api.model
    def fetch_leads(self):
        start_time = time()
        max_duration = 100

        IrConfig = self.env['ir.config_parameter'].sudo()
        access_token = IrConfig.get_param('meta.access_token')

        if not access_token:
            _logger.error("Access token is missing.")
            return

        try:
            pages_resp = requests.get(
                'https://graph.facebook.com/v23.0/me/accounts',
                params={'access_token': access_token},
                timeout=20
            )
        except Exception:
            _logger.exception("Error while fetching pages")
            return

        if pages_resp.status_code != 200:
            _logger.error("Failed to fetch pages: %s", pages_resp.text)
            return

        pages = pages_resp.json().get('data', [])

        for page in pages:
            if time() - start_time > max_duration:
                return

            page_id = page.get('id')
            page_name = page.get('name')
            page_token = page.get('access_token')

            # -----------------------------
            # Fetch Forms
            # -----------------------------
            try:
                forms_resp = requests.get(
                    f"https://graph.facebook.com/v23.0/{page_id}/leadgen_forms",
                    params={'access_token': page_token},
                    timeout=20
                )
            except Exception:
                _logger.exception("Error fetching forms")
                continue

            if forms_resp.status_code != 200:
                continue

            forms = forms_resp.json().get('data', [])

            for form in forms:
                if time() - start_time > max_duration:
                    return

                form_id = form.get('id')
                form_name = form.get('name')

                # -----------------------------
                # Fetch Leads
                # -----------------------------
                try:
                    leads_resp = requests.get(
                        f"https://graph.facebook.com/v23.0/{form_id}/leads",
                        params={'access_token': page_token},
                        timeout=20
                    )
                except Exception:
                    _logger.exception("Error fetching leads")
                    continue

                if leads_resp.status_code != 200:
                    continue

                leads = leads_resp.json().get('data', [])
                print("===============leads",leads)

                for lead in leads:
                    print("=========lead",lead)
                    if time() - start_time > max_duration:
                        return

                    fb_lead_id = lead.get('id')
                    fb_time = lead.get("created_time")
                    field_data = lead.get('field_data', [])

                    # -----------------------------
                    # Parse fields
                    # -----------------------------
                    lead_vals = {}
                    for field in field_data:
                        key = field.get('name')
                        value = field.get('values', [None])[0]
                        if key and value:
                            lead_vals[key] = value

                    contact_name = (
                        lead_vals.get('full_name')
                        or lead_vals.get('name')
                        or lead_vals.get('first_name')
                    )

                    email = lead_vals.get("email") or lead_vals.get("work_email")
                    phone = lead_vals.get("phone_number")

                    # -----------------------------
                    # Date conversion
                    # -----------------------------
                    created_date = False
                    if fb_time:
                        try:
                            dt = datetime.strptime(fb_time, "%Y-%m-%dT%H:%M:%S%z")
                            created_date = dt.replace(tzinfo=None)
                        except Exception:
                            _logger.exception("Date parsing failed")

                    # -----------------------------
                    # Country
                    # -----------------------------
                    country_rec = False
                    country_raw = (
                        lead_vals.get("country")
                        or lead_vals.get("country_name")
                        or lead_vals.get("country_code")
                    )

                    if country_raw:
                        domain = ["|", ("name", "ilike", country_raw), ("code", "=", country_raw.upper())]
                        country_rec = self.env['res.country'].sudo().search(domain, limit=1)

                        if not country_rec:
                            try:
                                country_rec = self.env['res.country'].sudo().create({
                                    "name": country_raw
                                })
                            except Exception:
                                _logger.exception("Country creation failed")

                    # -----------------------------
                    # UTM
                    # -----------------------------
                    source = self.env["utm.source"].sudo().search([("name", "=", "Facebook")], limit=1)
                    if not source:
                        source = self.env["utm.source"].sudo().create({"name": "Facebook"})

                    campaign = False
                    if page_name:
                        campaign = self.env["utm.campaign"].sudo().search([("name", "=", page_name)], limit=1)
                        if not campaign:
                            campaign = self.env["utm.campaign"].sudo().create({"name": page_name})

                    medium = False
                    if form_name:
                        medium = self.env["utm.medium"].sudo().search([("name", "=", form_name)], limit=1)
                        if not medium:
                            medium = self.env["utm.medium"].sudo().create({"name": form_name})

                    # -----------------------------
                    # Partner (FIXED OR)
                    # -----------------------------
                    partner = False

                    if email and phone:
                        partner = self.env["res.partner"].search(
                            ["|", ("email", "=", email), ("phone", "=", phone)],
                            limit=1
                        )
                    elif email:
                        partner = self.env["res.partner"].search([("email", "=", email)], limit=1)
                    elif phone:
                        partner = self.env["res.partner"].search([("phone", "=", phone)], limit=1)

                    if not partner and contact_name:
                        partner = self.env["res.partner"].create({
                            "name": contact_name,
                            "email": email,
                            "phone": phone,
                        })

                    # -----------------------------
                    # Lead Values
                    # -----------------------------
                    lead_name = contact_name or "Facebook Lead"

                    vals = {
                        "name": lead_name,
                        "facebook_lead_id": fb_lead_id,
                        "lead_create_date": created_date,
                        "form_name": form_name,
                        "email_from": email,
                        "phone": phone,
                        "country_id": country_rec.id if country_rec else False,
                        "partner_id": partner.id if partner else False,
                        "source_id": source.id,
                        "campaign_id": campaign.id if campaign else False,
                        "medium_id": medium.id if medium else False,
                        "company_id": self.env.company.id,
                    }

                    # -----------------------------
                    # SAFE UPSERT (MAIN FIX)
                    # -----------------------------
                    existing = self.env["crm.lead"].search(
                        [("facebook_lead_id", "=", fb_lead_id)],
                        limit=1
                    )

                    if existing:
                        update_vals = {
                            "campaign_id": vals["campaign_id"],
                            "medium_id": vals["medium_id"],
                            "source_id": vals["source_id"],
                            "form_name": vals["form_name"],
                        }

                        # ✅ Protect user changes
                        if not existing.email_from and email:
                            update_vals["email_from"] = email

                        if not existing.phone and phone:
                            update_vals["phone"] = phone

                        if not existing.partner_id and partner:
                            update_vals["partner_id"] = partner.id

                        if not existing.country_id and country_rec:
                            update_vals["country_id"] = country_rec.id

                        existing.write(update_vals)

                    else:
                        vals["user_id"] = self.env.user.id
                        vals["stage_id"] = self.env['crm.stage'].search(
                            [('sequence', '=', 1)], limit=1
                        ).id

                        self.env["crm.lead"].create(vals)

        _logger.info("Meta Lead Fetch Completed Successfully")

    # @api.model
    # def fetch_leads(self):
    #     start_time = time()
    #     max_duration = 100 
    #     IrConfig = self.env['ir.config_parameter'].sudo()
    #     access_token = IrConfig.get_param('meta.access_token')
    #     if not access_token:
    #         _logger.error("Access token is missing.")
    #         return
    #     pages_url = 'https://graph.facebook.com/v23.0/me/accounts'
    #     page_resp = requests.get(pages_url, params={'access_token': access_token})
    #     if page_resp.status_code != 200:
    #         _logger.error("Failed to fetch pages: %s", page_resp.text)
    #         return
    #     pages = page_resp.json().get('data', [])
    #     if not pages:
    #         _logger.warning("No pages found.")
    #         return
    #     for page in pages:
            
    #         if time() - start_time > max_duration:
    #             return
    #         page_id = page.get('id')
    #         page_name = page.get('name')
    #         page_access_token = page.get('access_token')
    #         # Fetch forms
    #         forms_url = f"https://graph.facebook.com/v23.0/{page_id}/leadgen_forms"
    #         form_resp = requests.get(forms_url, params={'access_token': page_access_token})
    #         if form_resp.status_code != 200:
    #             _logger.error("Failed to fetch forms for page %s: %s", page_name, form_resp.text)
    #             continue
    #         forms = form_resp.json().get('data', [])
    #         if not forms:
    #             continue
    #         for form in forms:
    #             if time() - start_time > max_duration:
    #                 return
    #             form_id = form.get('id')
    #             form_name = form.get('name')
    #             leads_url = f"https://graph.facebook.com/v23.0/{form_id}/leads"
    #             leads_resp = requests.get(leads_url, params={'access_token': page_access_token})
    #             if leads_resp.status_code != 200:
    #                 continue
    #             leads = leads_resp.json().get('data', [])
                
    #             if not leads:
    #                 continue
    #             for lead in leads:
                    
    #                 fb_lead_id = lead.get('id')
    #                 created_time_val = lead.get('created_time')
    #                 field_data = lead.get('field_data', [])
    #                 lead_vals = {}
    #                 for field in field_data:
    #                     key = field.get('name')
    #                     value = field.get('values', [None])[0]
    #                     if key and value:
    #                         lead_vals[key] = value
    #                 contact_name = lead_vals.get('full_name') or lead_vals.get('name') or lead_vals.get('first_name') or False
    #                 created_time_val = lead.get('created_time')
    #                 fb_time = lead.get("created_time")
    #                 created_date_clean = False

    #                 if fb_time:
    #                     try:
    #                         dt = datetime.strptime(fb_time, "%Y-%m-%dT%H:%M:%S%z")
    #                         dt = dt.replace(tzinfo=None)
    #                         created_date_clean = dt
    #                     except Exception as e:
    #                         _logger.exception("Error parsing Facebook date: %s", fb_time)
    #                         created_date_clean = fb_time
    #                 # country_raw = lead_vals.get("country") or lead_vals.get("country_name") or lead_vals.get("country_code")
    
    #                 # country_id = False
    #                 # if country_raw:
    #                 #     country_search_domain = [
    #                 #         "|",
    #                 #         ("name", "=ilike", country_raw),
    #                 #         ("code", "=ilike", country_raw)
    #                 #     ]
    #                 #     country_rec = self.env['res.country'].sudo().search(country_search_domain, limit=1)
    #                 #     if not country_rec:
    #                 #         try:
    #                 #             country_rec = self.env['res.country'].sudo().create({"name": country_raw})
    #                 #             _logger.info("Created res.country: %s", country_raw)
    #                 #         except Exception:
    #                 #             _logger.exception("Failed to create country %s", country_raw)
    #                 #             country_rec = False
    #                 #     if country_rec:
    #                 #         country_id = country_rec.id

    #                 country_raw = lead_vals.get("country") or lead_vals.get("country_name") or lead_vals.get("country_code")

    #                 country_id = False
    #                 country_rec = False

    #                 if country_raw:
    #                     # domain = ["|", ("name", "=ilike", country_raw), ("code", "=ilike", country_raw)]
    #                     domain = ["|", ("name", "ilike", country_raw), ("code", "=", country_raw.upper())]
                        
    #                     country_rec = self.env['res.country'].sudo().search(domain, limit=1)

    #                     if not country_rec:
    #                         try:
    #                             country_rec = self.env['res.country'].sudo().create({"name": country_raw})
    #                         except Exception:
    #                             _logger.exception("Failed to create country %s", country_raw)

    #                     if country_rec:
    #                         country_id = country_rec.id

    #                 source_rec = self.env["utm.source"].sudo().search([("name", "=", "Facebook")], limit=1)
    #                 if not source_rec:
    #                     source_rec = self.env["utm.source"].sudo().create({"name": "Facebook"})

    #                 campaign_id = False
    #                 if page_name:
    #                     campaign = self.env["utm.campaign"].sudo().search([("name", "=", page_name)], limit=1)
    #                     if not campaign:
    #                         campaign = self.env["utm.campaign"].sudo().create({"name": page_name})
    #                     campaign_id = campaign.id
                    
    #                 medium_id = False
    #                 if form_name:
    #                     medium = self.env["utm.medium"].sudo().search([("name", "=", form_name)], limit=1)
    #                     if not medium:
    #                         medium = self.env["utm.medium"].sudo().create({"name": form_name})
    #                     medium_id = medium.id


    #                 partner = None
    #                 email = lead_vals.get("email")
    #                 phone = lead_vals.get("phone_number")
    #                 if email or phone:
    #                     domain = []
    #                     if email: domain.append(("email", "=", email))
    #                     if phone: domain.append(("phone", "=", phone))
    #                     partner = self.env["res.partner"].search(domain, limit=1)
    #                 if not partner and contact_name:
    #                     partner = self.env["res.partner"].search([("name", "=", contact_name)], limit=1)
    #                 if not partner and contact_name:
    #                     partner_vals = {
    #                         "name": contact_name,
    #                     }
    #                     if email: partner_vals["email"] = email
    #                     if phone: partner_vals["phone"] = phone
    #                     partner = self.env["res.partner"].create(partner_vals)
    #                     _logger.info("Created partner %s from Facebook lead", contact_name)
    #                 if contact_name:
    #                     lead_name = f"{contact_name}"
    #                 else:
    #                     lead_name = "Facebook Lead Opportunity"
    #                 vals = {
    #                     "name": lead_name,
    #                     "facebook_lead_id": fb_lead_id,
    #                     "lead_create_date": created_date_clean,
    #                     "form_name": form_name,
    #                     "first_name": lead_vals.get("first_name"),
    #                     "phone_number": lead_vals.get("phone_number"),
    #                     "country_id": country_rec.id if country_rec else '',
    #                     "function": lead_vals.get("job_title"),
    #                     "email_from": lead_vals.get("email"),
    #                     "phone": lead_vals.get("phone_number"),
    #                     "user_id": self.env.user.id,
    #                     "company_id": self.env.company.id,
    #                     "source_id":source_rec.id,
    #                     "stage_id": self.env['crm.stage'].search([('sequence', '=', 1)], limit=1).id,
    #                     "partner_id": partner.id if partner else False,
    #                     "campaign_id": campaign_id,
    #                     "medium_id": medium_id,
    #                 }
    #                 # existing = self.env["crm.lead"].search([("facebook_lead_id", "=", fb_lead_id)], limit=1)
    #                 # if existing:
    #                 #     existing.write(vals)
    #                 # else:
    #                 #     self.env["crm.lead"].create(vals)
    #                 if existing:
    #                     update_vals = {
    #                         "campaign_id": campaign_id,
    #                         "medium_id": medium_id,
    #                         "source_id": source_rec.id,
    #                         "form_name": form_name,
    #                     }

    #                     # Only update if not already assigned
    #                     if not existing.user_id:
    #                         update_vals["user_id"] = self.env.user.id

    #                     # Only update email if empty
    #                     if not existing.email_from:
    #                         update_vals["email_from"] = lead_vals.get("email")

    #                     # Only update phone if empty
    #                     if not existing.phone:
    #                         update_vals["phone"] = lead_vals.get("phone_number")

    #                     existing.write(update_vals)
    #                 else:
    #                     self.env["crm.lead"].create(vals)
    #     _logger.info("Lead Fetching Done.")

  




    