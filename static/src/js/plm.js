odoo.define('plm', function (require) {
"use strict";

var core = require('web.core');
var data = require('web.data');
var form_common = require('web.form_common');
var formats = require('web.formats');
var Model = require('web.DataModel');
var time = require('web.time');
var utils = require('web.utils');

var QWeb = core.qweb;
var _t = core._t;

var PlmSheet = form_common.FormWidget.extend(form_common.ReinitializeWidgetMixin, {
    events: {
        "click .oe_timesheet_weekly_account a": "go_to",
    },
    ignore_fields: function() {
        return ['line_id'];
    },
    init: function() {
        this._super.apply(this, arguments);
        this.set({
            sheets: [],
            date_from: false,
            date_to: false,
        });

        this.field_manager.on("field_changed:plm_units", this, this.query_sheets);
        this.field_manager.on("field_changed:date_from", this, function() {
            this.set({"date_from": time.str_to_date(this.field_manager.get_field_value("date_from"))});
        });
        this.field_manager.on("field_changed:date_to", this, function() {
            this.set({"date_to": time.str_to_date(this.field_manager.get_field_value("date_to"))});
        });
        this.field_manager.on("field_changed:user_id", this, function() {
            this.set({"user_id": this.field_manager.get_field_value("user_id")});
        });
        this.on("change:sheets", this, this.update_sheets);
        this.res_o2m_drop = new utils.DropMisordered();
        this.render_drop = new utils.DropMisordered();
        this.description_line = _t("/");
    },
    go_to: function(event) {
        var id = JSON.parse($(event.target).data("id"));
        this.do_action({
            type: 'ir.actions.act_window',
            res_model: "tranche.horaire",
            res_id: id,
            views: [[false, 'form']],
        });
    },
    query_sheets: function() {
        if (this.updating) {
            return;
        }
        this.querying = true;
        var commands = this.field_manager.get_field_value("plm_units");
        var self = this;
        this.res_o2m_drop.add(new Model(this.view.model).call("resolve_2many_commands", 
                ["plm_units", commands, [], new data.CompoundContext()]))
            .done(function(result) {
                self.set({sheets: result});
                self.querying = false;
            });
    },
    update_sheets: function() {
        if(this.querying) {
            return;
        }
        this.updating = true;

        var commands = [form_common.commands.delete_all()];
        _.each(this.get("sheets"), function (_data) {
            var data = _.clone(_data);
            if(data.id) {
                commands.push(form_common.commands.link_to(data.id));
                commands.push(form_common.commands.update(data.id, data));
            } else {
                commands.push(form_common.commands.create(data));
            }
        });

        var self = this;
        this.field_manager.set_values({'plm_units': commands}).done(function() {
            self.updating = false;
        });
    },
    initialize_field: function() {
        form_common.ReinitializeWidgetMixin.initialize_field.call(this);
        this.on("change:sheets", this, this.initialize_content);
        this.on("change:date_to", this, this.initialize_content);
        this.on("change:date_from", this, this.initialize_content);
        this.on("change:user_id", this, this.initialize_content);
    },
    initialize_content: function() {
        if(this.setting) {
            return;
        }

        // don't render anything until we have date_to and date_from
        if (!this.get("date_to") || !this.get("date_from")) {
            return;
        }

        // it's important to use those vars to avoid race conditions
        var dates;
        var projects;
        var project_names;
        var default_get;
        var self = this;
        return this.render_drop.add(new Model("plm.unit").call("default_get", [
            ['value','date','name','user_id','unit_amount','tranche_horaire_id','coef'],
            new data.CompoundContext({'user_id': self.get('user_id')})
        ]).then(function(result) {
            default_get = result;
            // calculating dates
            dates = [];
            var start = self.get("date_from");
            var end = self.get("date_to");
            while (start <= end) {
                dates.push(start);
                var m_start = moment(start).add(1, 'days');
                start = m_start.toDate();
            }
            // group by project
            projects = _.chain(self.get("sheets"))
            .map(_.clone)
            .each(function(el) {
                // much simpler to use only the id in all cases
                if (typeof(el.tranche_horaire_id) === "object") {
                    el.tranche_horaire_id = el.tranche_horaire_id[0];
                }
            })
            .groupBy("tranche_horaire_id").value();
            var project_ids = _.map(_.keys(projects), function(el) { return el === "false" ? false : Number(el); });

            projects = _(projects).chain().map(function(lines, tranche_horaire_id) {
                var projects_defaults = _.extend({}, default_get, (projects[tranche_horaire_id] || {}).value || {});
                // group by days
                tranche_horaire_id = (tranche_horaire_id === "false")? false : Number(tranche_horaire_id);
                var index = _.groupBy(lines, "date");
                var days = _.map(dates, function(date) {
                    var day = {day: date, lines: index[time.date_to_str(date)] || []};
                    // add line where we will insert/remove hours
                    var to_add = _.find(day.lines, function(line) { return line.name === self.description_line; });
                    if (to_add) {
                        day.lines = _.without(day.lines, to_add);
                        day.lines.unshift(to_add);
                    } else {
                        day.lines.unshift(_.extend(_.clone(projects_defaults), {
                            name: self.description_line,
                            unit_amount: 0,
                            date: time.date_to_str(date),
                            tranche_horaire_id: tranche_horaire_id,
                        }));
                    }
                    return day;
                });
                return {project: tranche_horaire_id, days: days, projects_defaults: projects_defaults};
            }).value();

            // we need the name_get of the projects
            return new Model("tranche.horaire").call("name_get", [_.pluck(projects, "project"),
                new data.CompoundContext()]).then(function(result) {
                project_names = {};
                _.each(result, function(el) {
                    project_names[el[0]] = el[1];
                });
                projects = _.sortBy(projects, function(el) {
                    return project_names[el.project];
                });
            });

        })).then(function(result) {
            // we put all the gathered data in self, then we render
            self.dates = dates;
            self.projects = projects;
            self.project_names = project_names;
            self.default_get = default_get;
            //real rendering
            self.display_data();
        });
    },
    destroy_content: function() {
        if (this.dfm) {
            this.dfm.destroy();
            this.dfm = undefined;
        }
    },
    is_valid_value:function(value){
        this.view.do_notify_change();
        var split_value = value.split(":");
        var valid_value = true;
        if (split_value.length > 2) {
            return false;
        }
        _.detect(split_value,function(num){
            if(isNaN(num)) {
                valid_value = false;
            }
        });
        return valid_value;
    },

    display_data: function() {
        var self = this;
        self.$el.html(QWeb.render("plm.PlmSheet", {widget: self}));
        _.each(self.projects, function(project) {
            _.each(_.range(project.days.length), function(day_count) {
                if (!self.get('effective_readonly')) {
                    self.get_box(project, day_count).val(self.sum_box(project, day_count, true)).change(function() {
                        var num = $(this).val();
                        if (self.is_valid_value(num) && num !== 0) {
                            num = Number(self.parse_client(num));
                        }
                        if (isNaN(num)) {
                            $(this).val(self.sum_box(project, day_count, true));
                        } else {
                            project.days[day_count].lines[0].unit_amount += num - self.sum_box(project, day_count);
                            if(!isNaN($(this).val())){
                                $(this).val(self.sum_box(project, day_count, true));
                            }

                            self.display_totals();
                            self.sync();
                        }
                    });
                } else {
                    self.get_box(project, day_count).html(self.sum_box(project, day_count, true));
                }
            });
        });

        self.display_totals();
        if(!this.get('effective_readonly')) {
            this.init_add_project();
        }
    },
    init_add_project: function() {
        if (this.dfm) {
            this.dfm.destroy();
        }

        var self = this;
        this.$(".oe_timesheet_weekly_add_row").show();
        this.dfm = new form_common.DefaultFieldManager(this);
        this.dfm.extend_field_desc({
            tranche_horaire: {
                relation: "tranche.horaire",
            },
        });
        var FieldMany2One = core.form_widget_registry.get('many2one');
        this.project_m2o = new FieldMany2One(this.dfm, {
            attrs: {
                name: "tranche_horaire",
                type: "many2one",
                domain: [
                    ['id', 'not in', _.pluck(this.projects, "project")],
                ],
                modifiers: '{"required": true}',
            },

        });

        this.project_m2o.prependTo(this.$(".o_add_timesheet_line > div")).then(function() {
            self.project_m2o.$el.addClass('oe_edit_only');
        });

        this.$(".oe_timesheet_button_add").click(function() {
            var id = self.project_m2o.get_value();
            if (id === false) {
                self.dfm.set({display_invalid_fields: true});
                return;
            }

            var ops = self.generate_o2m_value();
            ops.push(_.extend({}, self.default_get, {
                name: self.description_line,
                unit_amount: 0,
                date: time.date_to_str(self.dates[0]),
                tranche_horaire_id: id,
            }));

            self.set({sheets: ops});
            self.destroy_content();
        });
    },

    get_box: function(project, day_count) {
        return this.$('[data-project="' + project.project + '"][data-day-count="' + day_count + '"]');

    },


    sum_box: function(project, day_count, show_value_in_hour) {        
        var line_total = 0;
        _.each(project.days[day_count].lines, function(line) {
            line_total += line.unit_amount;
        });
        return line_total
    },

    get_sum: function(project, day_count,show_value_in_hour) {
        var line_total = 0;
        _.each(project.days[day_count].lines, function(line) {
            var l = line.unit_amount*line.coef
            line_total += l
        });
        return isNaN(line_total) ? 0 : line_total;
    },


    display_totals: function() {
        var self = this;
        var day_tots = _.map(_.range(self.dates.length), function() { return 0; });
        var super_tot = 0;
        _.each(self.projects, function(project) {
            var acc_tot = 0;
            _.each(_.range(self.dates.length), function(day_count) {
                var sum = self.sum_box(project, day_count);
                var sum2 = self.get_sum(project, day_count);
                acc_tot += sum;
                day_tots[day_count] += sum2;
                super_tot += sum2;
                console.log(sum2)
            });
            self.$('[data-project-total="' + project.project + '"]').html(acc_tot);
        });
        _.each(_.range(self.dates.length), function(day_count) {
            self.$('[data-day-total="' + day_count + '"]').html(day_tots[day_count]);
        });
            this.$('.oe_timesheet_weekly_supertotal').html(super_tot);
    },


    sync: function() {
        this.setting = true;
        this.set({sheets: this.generate_o2m_value()});
        this.setting = false;
    },
    //converts hour value to float
    parse_client: function(value) {
        return formats.parse_value(value, { type:"float_time" });
    },
    //converts float value to hour
    format_client:function(value){
        return formats.format_value(value, { type:"float_time" });
    },
    generate_o2m_value: function() {
        var ops = [];
        var ignored_fields = this.ignore_fields();
        _.each(this.projects, function(project) {
            _.each(project.days, function(day) {
                _.each(day.lines, function(line) {
                    if (line.unit_amount !== 0) {
                        var tmp = _.clone(line);
                        _.each(line, function(v, k) {
                            if (v instanceof Array) {
                                tmp[k] = v[0];
                            }
                        });
                        // we remove line_id as the reference to the _inherits field will no longer exists
                        tmp = _.omit(tmp, ignored_fields);
                        ops.push(tmp);
                    }
                });
            });
        });
        return ops;
    },
});

core.form_custom_registry.add('PLMsheet', PlmSheet);

});
