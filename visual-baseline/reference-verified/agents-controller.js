define(['jquery', 'bootstrap', 'backend', 'table', 'form'], function ($, undefined, Backend, Table, Form) {

    var Controller = {
        index: function () {
            // 初始化表格参数配置
            Table.api.init({
                extend: {
                    index_url: 'agent/index',
                    add_url: 'agent/add',
                    edit_url: 'agent/edit',
                    del_url: 'agent/del',
                    multi_url: 'agent/multi',
                    ossedit_url: 'agent/ossedit',
                    table: 'agent',
                }
            });

            var table = $("#table");

            // 初始化表格
            table.bootstrapTable({
                url: $.fn.bootstrapTable.defaults.extend.index_url,
                pk: 'id',
                sortName: 'id',
                columns: [
                    [
                        {checkbox: true},
                        {field: 'id', title: __('Id'), operate: false, sortable: true},
						{field: 'name', title: '代理商名称', operate: 'LIKE', align: 'left'},
						/* {field: 'parent_name', title: '上级代理商', operate: 'LIKE', align: 'left'},
						{field: 'user_name', title: '代理商账号', operate: 'LIKE'}, */
				// 		{field: 'total_coin', title: '累计用户金币收益', operate: false,formatter: function (value) {
    //                         return value*1;
    //                     }},
						//{field: 'total_coin_month', title: '本月用户金币收益', operate: false,formatter: function (value) {
                        //    return value*1;
                        //}},
						//{field: 'total_coin_day', title: '今日用户金币收益', operate: false,formatter: function (value) {
                        //    return value*1;
                        //}},
						{
							field: 'buttons',
							width: "120px",
							title: '游戏管理',
							table: table,
							events: Table.api.events.operate,
							buttons: [
							    {
									name: 'ossedit',
									title: 'OSS配置',
									text: 'OSS配置',
									icon: '',
									classname: 'btn btn-success btn-xs btn-detail btn-dialog',
									url: 'agent/ossedit'
								},
								{
									name: 'dash',
									text: '进入',
									title: '游戏管理',
									classname: 'btn btn-xs btn-info btn-addtabs',
									icon: 'fa fa-gamepad',
									url: 'agents/dash/index/agent_id/{ids}'
								}
							],
							operate: false,
							formatter:function (value, row, index) {
								var that = $.extend({}, this);
								var table = $(that.table).clone(true);
								$(table).data("operate-edit", null);
								$(table).data("operate-del", null);
								if (row.parent_id > 0) {
									$(table).data("operate-dash", null);
                                }
								that.table = table;
								return Table.api.formatter.operate.call(that, value, row, index);
                            },
						},
						{field: 'user_id', title: '穿山甲user_id', visible: false, operate: false},
						{field: 'role_id', title: '穿山甲role_id', visible: false, operate: false},
						{field: 'security_key', title: '穿山甲security_key', visible: false, operate: false},
						{field: 'status', title: '状态', searchList: {"1": '启用', "0": '禁用'}, formatter: Table.api.formatter.label},
                        {field: 'create_time', title: __('Createtime'), formatter: Table.api.formatter.datetime, operate: 'RANGE', addclass: 'datetimerange', sortable: true},
                        {field: 'update_time', title: __('Updatetime'), formatter: Table.api.formatter.datetime, operate: 'RANGE', addclass: 'datetimerange', sortable: true, visible: false},
                        {field: 'operate', title: __('Operate'), table: table, events: Table.api.events.operate, formatter: Table.api.formatter.operate}
                    ]
                ],
                pagination: true,
                search: false,
                commonSearch: true,
            });

            // 为表格绑定事件
            Table.api.bindevent(table);
        },
        add: function () {
            Controller.api.bindevent();
        },
        edit: function () {
            Controller.api.bindevent();
        },
        ossedit: function () {
		    Controller.api.bindevent();
        },
        api: {
            bindevent: function () {
                Form.api.bindevent($("form[role=form]"));
            }
        }
    };
    return Controller;
});
