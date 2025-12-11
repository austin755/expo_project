from odoo import models, fields, api

class CrmLead(models.Model):
    _inherit = 'crm.lead'

    facebook_lead_id = fields.Char(string="Facebook Lead ID", help="Unique ID of the lead from Facebook")
    lead_create_date = fields.Char(string='Lead Create Date')
    phone_number = fields.Char(string="Whatsapp Number")
    first_name = fields.Char(string="First Name")
    country= fields.Char(string="Country")
    job_title = fields.Char(string="Job Title")
    form_name = fields.Char(string="Form Name")

    

    