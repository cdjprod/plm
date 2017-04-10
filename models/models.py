# -*- coding: utf-8 -*-

from odoo import models, fields, api, tools
from odoo.tools.translate import _
from odoo.exceptions import UserError, ValidationError
from datetime import date, timedelta ,datetime
import time
from dateutil.relativedelta import relativedelta
from odoo.tools.sql import drop_view_if_exists
from odoo.report import report_sxw


class plm(models.Model):
    _name = 'plm.plm'

    def _default_date_from(self):
        return fields.Date.context_today(self)

    def _default_date_to(self):
        return (datetime.today() + relativedelta(months=+1, day=1, days=-1)).strftime('%Y-%m-%d')

    def _default_auteur(self):
        emp_ids = self.env['res.users'].search([('id', '=', self.env.uid)])
        return emp_ids and emp_ids[0] or False

    name = fields.Char('Titre')
    chaine = fields.Char('Chaine')
    campagne = fields.Char('Campagne')
    date_from = fields.Date(string='Date de début',required=True,default=_default_date_from,
        index=True)
    date_to = fields.Date(string='Date de fin', required=True,default=_default_date_to,
        index=True)
    user_id = fields.Many2one('res.users', string='Auteur', default=_default_auteur, required=True)

    plm_units = fields.One2many('plm.unit','plm')

    somme_total = fields.Integer('super Total',compute="get_total")
    total_display = fields.Integer('Total',compute="_compute_total_display")

    state = fields.Selection([
        ('new', 'Nouveau'),
        ('draft', 'Ouvertes'),
        ('confirm', 'En attente d\'approbation'),
        ('done', 'Confirmé')], default='new', track_visibility='onchange',
        string='Status', required=True, readonly=True, index=True)

    tranche_horaire_ids = fields.Many2many('tranche.horaire',compute="get_tranche_horaires_ids")

    option = fields.Selection([
        ('tv', 'TV'),
        ('rd', 'RD')],string="Option")

    @api.multi
    def get_table(self):
        for record in self:
            Liste = []
            start = record.date_from
            end = record.date_to
            delta = fields.Date.from_string(end) - fields.Date.from_string(start)
            dates_list= []
            for i in range(delta.days + 1):
                dates_list.append(fields.Date.to_string(fields.Date.from_string(start)+timedelta(days=i)))
            dates_liste = ["T - H"]
            for i in range(delta.days + 1):
                daty = (fields.Date.from_string(start)+timedelta(days=i)).day
                dates_liste.append(daty)
            dates_liste.append('Total')    
            Liste.append(dates_liste)
            for tranche in record.tranche_horaire_ids:
                liste = []
                liste.append(tranche.name)
                for d in dates_list:
                    somme=0
                    for i in record.plm_units:
                        if i.date == d and i.tranche_horaire_id.id ==tranche.id:
                            somme+=i.unit_amount                      
                    liste.append(somme)
                liste.append(sum(liste[1:]))
                Liste.append(liste)
            Liste.append(record.get_somme_total())
            return Liste

    @api.multi
    def _compute_total_display(self):
        for record in self:
            record.total_display = record.get_somme_total()[-1]


    @api.multi
    def get_somme_total(self):
        for record in self:
            Liste = ['Total']
            dates_list = []
            start = record.date_from
            end = record.date_to
            delta = fields.Date.from_string(end) - fields.Date.from_string(start)
            for i in range(delta.days + 1):
                dates_list.append(fields.Date.to_string(fields.Date.from_string(start)+timedelta(days=i)))
            for d in dates_list:
                somme = 0
                Dict = record.get_list_per_day()
                if Dict.get(d):
                    somme += sum([i.unit_amount * i.coef for i in Dict[d]])
                Liste.append(somme)
            Liste.append(sum(Liste[1:]))
            return Liste

    @api.multi
    def get_tranche_horaires_ids(self):
        for record in self:
            List = []
            for r in record.plm_units:
                if r.tranche_horaire_id in List:
                    continue
                else:
                    List.append(r.tranche_horaire_id.id)
            record.tranche_horaire_ids = List




    @api.multi
    def get_list_per_project(self):
        for record in self:
            Dict = {}
            for i in record.plm_units:
                if Dict.get(i.tranche_horaire_id):
                    Dict[i.tranche_horaire_id].append(i)
                else:
                    Dict[i.tranche_horaire_id] = [i]
           




    @api.multi
    def get_list_per_day(self):
        for record in self:
            Dict = {}
            for i in record.plm_units:
                if Dict.get(i.date):
                    Dict[i.date].append(i)
                else:
                    Dict[i.date] = [i]
            return Dict


                
    @api.multi
    def get_total(self):
        for record in self:
            s = 0
            for i in record.plm_units:
                s += i.unit_amount * i.coef

    @api.model
    def create(self, vals):
        res = super(plm, self).create(vals)
        res.write({'state': 'draft'})
        return res

    @api.multi
    def action_draft(self):
        self.write({'state': 'draft'})
        return True

    @api.multi
    def action_draft_confirm(self):
        if not self.env.user.has_group('plm.group_responsable_plm'):
            raise UserError(_('Seule les responsables peuvent réfuser'))
        self.write({'state': 'draft'})
        return True

    @api.multi
    def action_confirm(self):
        self.write({'state': 'confirm'})
        return True

    @api.multi
    def action_done(self):
        if not self.env.user.has_group('plm.group_responsable_plm'):
            raise UserError(_('Seule les responsables peuvent approuver'))
        self.write({'state': 'done'})

    


class plm_unit(models.Model):
    _name = 'plm.unit'

    name =fields.Char('Déscription')
    unit_amount = fields.Integer('Valeur')
    date = fields.Date(string='Date',required=True)
    tranche_horaire_id =fields.Many2one('tranche.horaire', string='Tranche horaire', required=True)
    plm = fields.Many2one('plm.plm', string='Sheet', store=True)
    user_id = fields.Many2one('res.users', string='Auteur')
    coef = fields.Float('Pression',compute="get_pression")
    chaine= fields.Char('Chaine',related="plm.chaine")
    option = fields.Selection([
        ('tv', 'TV'),
        ('rd', 'RD')],related="plm.option", string="Option")


    @api.depends('chaine','chaine')
    def get_pression(self):
        for record in self:
            liste={
                1:'janvier',
                2:'février',
                3:'mars',
                4:'avril',
                5:'mai',
                6:'juin',
                7:'juillet',
                8:'août',
                9:'septembre',
                10:'octobre',
                11:'novembre',
                12:'décembre',
            }
            if record.option == "rd":
                mois = (fields.Date.from_string(record.date)).month
                if 0<=(fields.Date.from_string(record.date)).weekday()<=4:
                    val = self.env['mmrd.ensemble'].search([('name', '=',record.chaine),('slotens','=',record.tranche_horaire_id.name),('jour','=','semaine'),('mois','=',liste[mois])])
                    if val:
                        record.coef = val.tauxens
                    else:
                        val=self.env['mmrd.ensemble'].search([('name', '=',record.chaine),('slotens','=',record.tranche_horaire_id.name),('jour','=','semaine'),('mois','=',liste[mois-1])])
                        if val:
                            record.coef = val.tauxens
                if (fields.Date.from_string(record.date)).weekday()==5:
                    val = self.env['mmrd.ensemble'].search([('name', '=',record.chaine),('slotens','=',record.tranche_horaire_id.name),('jour','=','samedi'),('mois','=',liste[mois])])
                    if val:
                        record.coef = val.tauxens
                    else:
                        val=self.env['mmrd.ensemble'].search([('name', '=',record.chaine),('slotens','=',record.tranche_horaire_id.name),('jour','=','samedi'),('mois','=',liste[mois-1])])
                        if val:
                            record.coef = val.tauxens
                if (fields.Date.from_string(record.date)).weekday()==6:
                    val = self.env['mmrd.ensemble'].search([('name', '=',record.chaine),('slotens','=',record.tranche_horaire_id.name),('jour','=','dimanche'),('mois','=',liste[mois])])
                    if val:
                        record.coef = val.tauxens
                    else:
                        val=self.env['mmrd.ensemble'].search([('name', '=',record.chaine),('slotens','=',record.tranche_horaire_id.name),('jour','=','dimanche'),('mois','=',liste[mois-1])])
                        if val:
                            record.coef = val.tauxens

            if record.option == "tv":
                mois = (fields.Date.from_string(record.date)).month
                if 0<=(fields.Date.from_string(record.date)).weekday()<=4:
                    val = self.env['mm.ensemble'].search([('name', '=',record.chaine),('slotens','=',record.tranche_horaire_id.name),('jour','=','semaine'),('mois','=',liste[mois])])
                    if val:
                        record.coef = val.tauxens
                    else:
                        val=self.env['mm.ensemble'].search([('name', '=',record.chaine),('slotens','=',record.tranche_horaire_id.name),('jour','=','semaine'),('mois','=',liste[mois-1])])
                        if val:
                            record.coef = val.tauxens
                if (fields.Date.from_string(record.date)).weekday()==5:
                    val = self.env['mm.ensemble'].search([('name', '=',record.chaine),('slotens','=',record.tranche_horaire_id.name),('jour','=','samedi'),('mois','=',liste[mois])])
                    if val:
                        record.coef = val.tauxens
                    else:
                        val=self.env['mm.ensemble'].search([('name', '=',record.chaine),('slotens','=',record.tranche_horaire_id.name),('jour','=','samedi'),('mois','=',liste[mois-1])])
                        if val:
                            record.coef = val.tauxens
                if (fields.Date.from_string(record.date)).weekday()==6:
                    val = self.env['mm.ensemble'].search([('name', '=',record.chaine),('slotens','=',record.tranche_horaire_id.name),('jour','=','dimanche'),('mois','=',liste[mois])])
                    if val:
                        record.coef = val.tauxens
                    else:
                        val=self.env['mm.ensemble'].search([('name', '=',record.chaine),('slotens','=',record.tranche_horaire_id.name),('jour','=','dimanche'),('mois','=',liste[mois-1])])
                        if val:
                            record.coef = val.tauxens
                    
    

class tranche_horaire(models.Model):
    _name = 'tranche.horaire'
    name = fields.Char('Tranche horaire')


class Res_users(models.Model):
    _inherit = 'res.users'

    equipe = fields.Many2one('equipe.equipe','Equipe')


class Equipe(models.Model):
    _name = 'equipe.equipe'
    name = fields.Char('Equipe')

class ModelImpression(models.Model):
    _name =  "model.impression"

    name = fields.Text('Description')
    logo = fields.Binary("Logo")
    actif = fields.Boolean("Actif")




class PlmReport(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):

        super(PlmReport, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            '_load': self._load,
            '_get_variable': self._get_variable,
            '_set_variable': self._set_variable,
        })
        self.context = context

    def _load(self):
        env = api.Environment(self.cr, self.uid, {})
        active_ids = env.get('active_ids', [])
        print('context',self.localcontext)
        valeur = env['plm.plm'].browse(self.localcontext['objects'].id)
        valeur = valeur.get_table()
        valeur1 = valeur[0]
        valeurs = valeur[1:-1]
        valeur2 = valeur[-1]
        logo = env['model.impression'].search([('actif','=',True)])
        if logo:
            logo = env['model.impression'].browse(logo[0].id)
        print('logo',logo)
        self._set_variable('value', valeurs)
        self._set_variable('value1', valeur1)
        self._set_variable('value2', valeur2)
        self._set_variable('logo',logo)

    def _set_variable(self, variable, valeur):
        self.localcontext.update({variable: valeur})

    def _get_variable(self, variable):
        return self.localcontext[variable]

    def set_context(self, objects, data, ids):
        super(PlmReport, self).set_context(objects, data, ids)
        self._load()


class PlmReportWrapper(models.AbstractModel):
    _name = 'report.plm.report_plm_plm'
    _inherit = 'report.abstract_report'
    _template = 'plm.report_plm_plm'
    _wrapped_report_class = PlmReport







