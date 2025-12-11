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
        # Get All Pages
        pages_url = 'https://graph.facebook.com/v23.0/me/accounts'
        page_resp = requests.get(pages_url, params={'access_token': access_token})
        if page_resp.status_code != 200:
            _logger.error("Failed to fetch pages: %s", page_resp.text)
            return
        pages = page_resp.json().get('data', [])
        if not pages:
            _logger.warning("No pages found.")
            return
        for page in pages:
            if time() - start_time > max_duration:
                return
            page_id = page.get('id')
            page_name = page.get('name')
            page_access_token = page.get('access_token')
            # Fetch forms
            forms_url = f"https://graph.facebook.com/v23.0/{page_id}/leadgen_forms"
            form_resp = requests.get(forms_url, params={'access_token': page_access_token})
            if form_resp.status_code != 200:
                _logger.error("Failed to fetch forms for page %s: %s", page_name, form_resp.text)
                continue
            forms = form_resp.json().get('data', [])
            if not forms:
                continue
            for form in forms:
                if time() - start_time > max_duration:
                    return
                form_id = form.get('id')
                form_name = form.get('name')
                leads_url = f"https://graph.facebook.com/v23.0/{form_id}/leads"
                leads_resp = requests.get(leads_url, params={'access_token': page_access_token})
                if leads_resp.status_code != 200:
                    continue
                leads = leads_resp.json().get('data', [])
                if not leads:
                    continue
                for lead in leads:
                    fb_lead_id = lead.get('id')
                    created_time_val = lead.get('created_time')
                    field_data = lead.get('field_data', [])
                    lead_vals = {}
                    for field in field_data:
                        key = field.get('name')
                        value = field.get('values', [None])[0]
                        if key and value:
                            lead_vals[key] = value
                    contact_name = lead_vals.get('full_name') or lead_vals.get('name') or lead_vals.get('first_name') or False
                    # Find partner
                    partner = None
                    email = lead_vals.get("email")
                    phone = lead_vals.get("phone_number")
                    if email or phone:
                        domain = []
                        if email: domain.append(("email", "=", email))
                        if phone: domain.append(("phone", "=", phone))
                        partner = self.env["res.partner"].search(domain, limit=1)
                    if not partner and contact_name:
                        partner = self.env["res.partner"].search([("name", "=", contact_name)], limit=1)
                    if not partner and contact_name:
                        partner_vals = {
                            "name": contact_name,
                        }
                        if email: partner_vals["email"] = email
                        if phone: partner_vals["phone"] = phone
                        partner = self.env["res.partner"].create(partner_vals)
                        _logger.info("Created partner %s from Facebook lead", contact_name)
                    if contact_name:
                        lead_name = f"{contact_name}"
                    else:
                        lead_name = "Facebook Lead Opportunity"
                    vals = {
                        "name": lead_name,
                        "facebook_lead_id": fb_lead_id,
                        "lead_create_date": created_time_val,
                        "form_name": form_name,
                        "first_name": lead_vals.get("first_name"),
                        "phone_number": lead_vals.get("phone_number"),
                        "country": lead_vals.get("country"),
                        "job_title": lead_vals.get("job_title"),
                        "email_from": lead_vals.get("email"),
                        "phone": lead_vals.get("phone_number"),
                        "user_id": self.env.user.id,
                        "company_id": self.env.company.id,
                        "stage_id": self.env['crm.stage'].search([('sequence', '=', 1)], limit=1).id,
                        "partner_id": partner.id if partner else False,
                    }
                    existing = self.env["crm.lead"].search([("facebook_lead_id", "=", fb_lead_id)], limit=1)
                    if existing:
                        existing.write(vals)
                    else:
                        self.env["crm.lead"].create(vals)
        _logger.info("Lead Fetching Done.")