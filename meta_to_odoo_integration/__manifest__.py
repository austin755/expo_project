# -*- coding: utf-8 -*-
{
    'name': 'Meta To Odoo Integration',
    'version': '1.0',
    'depends': ['base','crm'],
    'author': 'NSPL',
    'category': 'Sales',
    'description': 'Sales',
    'data':[
        'security/ir.model.access.csv',
        'data/fetch_lead_cron.xml',
        'views/res_config_settings_view.xml',
		'views/crm_lead_view.xml', 
	],
    'license':'LGPL-3',
    'installable': True,
    'application': True,
}
