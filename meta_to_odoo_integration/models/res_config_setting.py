from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    meta_app_id = fields.Char("Meta App ID", config_parameter="meta.api_id")
    meta_app_secret = fields.Char("Meta App Secret",config_parameter="meta.app_secret")
    meta_access_token = fields.Char("Meta Access Token",config_parameter="meta.access_token")
    meta_ad_accounting_id = fields.Char('Meta Ad Accouting ID',config_parameter="meta.ad_accounting_id")