from odoo import http,models, fields, api
from odoo.http import request
import json


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    testing_name = fields.Char(string="Testing")


class WPLeadController(http.Controller):
    @http.route('/wordpress/webhook', type='json', auth='public', methods=['POST'], csrf=False)
    def wp_webhook(self):
        raw_data = request.httprequest.data
        
        def log_debug(message, data=None):
            request.env['ir.logging'].sudo().create({
                'name': 'WP Webhook Debug',
                'type': 'server',
                'dbname': request.env.cr.dbname,
                'level': 'DEBUG',
                'message': f"{message}: {data}" if data else message,
                'path': 'wordpress_webhook',
                'func': 'wp_webhook',
                'line': '0',
            })

        try:
            data = json.loads(raw_data.decode("utf-8"))
            log_debug("Data received from WordPress", data)
        except Exception as e:
            log_debug("Invalid JSON received", str(e))
            return {"status": "error", "message": "Invalid JSON received"}

        
        full_name = data.get("FullName")
        company_bs = data.get("CompanyName")
        country_bs = data.get("country-region")
        phone_bs = data.get("Phone")
        email_bs = data.get("Email")

        name_cu = data.get("your-name") or data.get("name") or data.get("fullname")
        email_cu = data.get("your-email") or data.get("email")
        phone_cu = data.get("your-phone") or data.get("phone")
        company_cu = data.get("company") or data.get("company-name")
        message_cu = data.get("your-message") or data.get("message")

        log_debug("Contact Us Form Data", {
            "name_cu": name_cu,
            "email_cu": email_cu,
            "phone_cu": phone_cu,
            "company_cu": company_cu,
            "message_cu": message_cu
        })

        final_name = full_name or name_cu or "Unknown"
        final_company = company_bs or company_cu or ""
        final_email = email_bs or email_cu or ""
        final_phone = phone_bs or phone_cu or ""
        final_country = country_bs
        
        final_message = message_cu or data.get("your-message") or ""

        log_debug("Merged Final Data", {
            "final_name": final_name,
            "final_company": final_company,
            "final_email": final_email,
            "final_phone": final_phone,
            "final_country": final_country,
            "final_message": final_message
        })
        source_website = request.env['utm.source'].sudo().search(
                [('name', '=', 'Website')],
                limit=1
            )
        if not source_website:
            source_website = request.env['utm.source'].sudo().create({
                'name': 'Website'
            })
        
        if isinstance(final_country, list):
            final_country = final_country[0] if final_country else False

        country_id = False
        if final_country:
            country = request.env["res.country"].sudo().search([
                ("name", "ilike", final_country)
            ], limit=1)
            
            country_id = country.id if country else False

        partner = request.env["res.partner"].sudo().search([
            ("name", "ilike", final_name)
        ], limit=1)

        if not partner:
            partner = request.env["res.partner"].sudo().create({
                "name": final_name,
                "company_name": final_company,
                "email": final_email,
                "phone": final_phone,
                "country_id": country_id,
            })

        lead_vals = {
            "name": final_name or final_company or "Website Lead",
            "contact_name": final_name,
            "partner_name": final_company,
            "partner_id": partner.id,
            "email_from": final_email,
            "phone": final_phone,
            "country_id": country_id,
            "description": f"Message:\n{final_message}".strip(),
            "source_id": source_website.id,
        }

        log_debug("Lead Values to Create", lead_vals)

        request.env["crm.lead"].sudo().create(lead_vals)

        return {"status": "success"}
