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

        # Helper function to log debug messages in production
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

        # -------------------------------
        # 1️⃣ Parse JSON safely
        # -------------------------------
        try:
            data = json.loads(raw_data.decode("utf-8"))
            log_debug("Data received from WordPress", data)
        except Exception as e:
            log_debug("Invalid JSON received", str(e))
            return {"status": "error", "message": "Invalid JSON received"}

        # -------------------------------
        # 2️⃣ Read fields from both forms
        # -------------------------------

        # Book a Stand fields
        full_name = data.get("FullName")
        company_bs = data.get("CompanyName")
        country_bs = data.get("country-region")
        phone_bs = data.get("Phone")
        email_bs = data.get("Email")

        # Contact Us form fields
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

        # -------------------------------
        # 3️⃣ Merge auto-detect form type
        # -------------------------------
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

        # -------------------------------
        # 4️⃣ Match country in Odoo
        # -------------------------------
        country_id = False
        if final_country:
            country = request.env["res.country"].sudo().search([
                ("name", "ilike", final_country)
            ], limit=1)
            country_id = country.id if country else False

        # -------------------------------
        # 5️⃣ Partner Create / Find
        # -------------------------------
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

        # -------------------------------
        # 6️⃣ Create CRM Lead
        # -------------------------------
        lead_vals = {
            "name": final_name or final_company or "Website Lead",
            "contact_name": final_name,
            "partner_name": final_company,
            "partner_id": partner.id,
            "email_from": final_email,
            "phone": final_phone,
            "country_id": country_id,
            "description": f"Message:\n{final_message}".strip(),
            "source_id": request.env.ref("crm.source_website", False).id
                         if request.env.ref("crm.source_website", False) else False,
        }

        log_debug("Lead Values to Create", lead_vals)

        request.env["crm.lead"].sudo().create(lead_vals)

        return {"status": "success"}


    # @http.route('/wordpress/webhook', type='json', auth='public', methods=['POST'], csrf=False)
    # def wp_webhook(self):
    #     raw_data = request.httprequest.data

        
    #     try:
    #         data = json.loads(raw_data.decode("utf-8"))
    #         print("==============data",data)
    #     except:
    #         return {"status": "error", "message": "Invalid JSON received"}

    #     # -------------------------------
    #     # 1️⃣ READ FIELDS FROM BOTH FORMS
    #     # -------------------------------

    #     # Book a Stand fields
    #     full_name = data.get("FullName")
    #     company_bs = data.get("CompanyName")
    #     country_bs = data.get("country-region")
    #     phone_bs = data.get("Phone")
    #     email_bs = data.get("Email")

    #     # Contact Us Form fields
    #     name_cu = data.get("your-name")
    #     print("=======name_cu======",name_cu)
    #     email_cu = data.get("your-email")
    #     print("=============email_cu",email_cu)
    #     phone_cu = data.get("your-phone")
    #     print("=============email_cu",phone_cu)
    #     company_cu = data.get("company")
    #     message_cu = data.get("your-message")

    #     # -------------------------------
    #     # 2️⃣ MERGE AUTO-DETECT FORM TYPE
    #     # -------------------------------
    #     final_name = full_name or name_cu
    #     print("======final_name====",final_name)
    #     final_company = company_bs or company_cu
    #     final_email = email_bs or email_cu
    #     print("======final_email====",final_email)
    #     final_phone = phone_bs or phone_cu
    #     final_country = country_bs
    #     final_message = message_cu or data.get("your-message") or ""

    #     # -------------------------------
    #     # 3️⃣ Match Country in Odoo
    #     # -------------------------------
    #     country_id = False
    #     if final_country:
    #         country = request.env["res.country"].sudo().search([
    #             ("name", "ilike", final_country)
    #         ], limit=1)
    #         country_id = country.id if country else False

    #     # -------------------------------
    #     # 4️⃣ Partner Create / Find
    #     # -------------------------------
    #     partner = None
    #     if final_name:
    #         partner = request.env["res.partner"].sudo().search([
    #             ("name", "ilike", final_name)
    #         ], limit=1)

    #     if not partner:
    #         partner = request.env["res.partner"].sudo().create({
    #             "name": final_name or "Unknown",
    #             "company_name": final_company or "",
    #             "email": final_email or "",
    #             "phone": final_phone or "",
    #             "country_id": country_id,
    #         })

    #     # -------------------------------
    #     # 5️⃣ Create CRM Lead
    #     # -------------------------------
    #     lead_vals = {
    #         "name": final_name or final_company or "Website Lead",
    #         "contact_name": final_name,
    #         "partner_name": final_company,
    #         "partner_id": partner.id,
    #         "email_from": final_email,
    #         "phone": final_phone,
    #         "country_id": country_id,
    #         "description": f"Message:\n{final_message}".strip(),
    #         "source_id": request.env.ref("crm.source_website", False).id if hasattr(request.env.ref("crm.source_website", False), 'id') else False,
    #     }
    #     print("==============lead",lead_vals)

    #     request.env["crm.lead"].sudo().create(lead_vals)

    #     return {"status": "success"}


# class WPLeadController(http.Controller):

#     @http.route('/wordpress/webhook', type='json', auth='public', methods=['POST'], csrf=False)
#     def wp_webhook(self):
#         raw_data = request.httprequest.data
#         try:
#             data = json.loads(raw_data.decode('utf-8')) 
#         except:
#             return {"status": "error", "message": "Invalid JSON"}

#         # Read CF7 fields
#         full_name = data.get('FullName')
#         name = data.get('your-name')
#         company = data.get('CompanyName')
#         country = data.get('country-region')
#         phone = data.get('Phone') or data.get('your-phone')
#         email = data.get('Email')  or data.get('your-email')
#         message = data.get('your-message')
    
#         # Find country in Odoo
#         country_id = False
#         if country:
#             country_rec = request.env['res.country'].sudo().search(
#                 [('name', 'ilike', country)], limit=1
#             )
#             country_id = country_rec.id if country_rec else False

#         search_name = full_name or name

#         partner = False
#         if search_name:
#             partner = request.env['res.partner'].sudo().search(
#                 [('name', 'ilike', search_name)], limit=1
#             )
#             if not partner:
#                 partner = request.env['res.partner'].sudo().create({
#                     'name': search_name,
#                     'company_name': company or '',
#                     'email': email or '',
#                     'phone': phone or '',
#                     'country_id': country_id or False,
#                     'is_company': False,
#                 })
                
#         final_description = f"Message:\n{message or ''}"

#         # Create CRM Lead
#         crm=request.env['crm.lead'].sudo().create({
#             'name': search_name or company,
#             'contact_name': search_name,
#             'partner_name': company,
#             'partner_id': partner.id if partner else False,
#             'email_from': email,
#             'phone': phone,
#             'description': final_description.strip(),
#             'country_id': country_id,
#         })

#         return {"status": "success"}
