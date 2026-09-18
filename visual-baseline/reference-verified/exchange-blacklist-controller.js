define(['jquery', 'bootstrap', 'backend', 'table', 'form'], function ($, undefined, Backend, Table, Form) {

    var Controller = {
        index: function () {

            // 初始化表格参数配置
            Table.api.init({
                extend: {
                    index_url: 'exchangehei/index',
                    edit_url: 'exchangehei/edit',
                    del_url: 'exchangehei/del',
                    multi_url: 'exchangehei/multi',
                    table: 'exchangehei',
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
						{field: 'receive_name', title: '收件人', formatter:Table.api.formatter.search},
						{field: 'receive_tel', title: '联系方式', formatter:Table.api.formatter.search},
						{field: 'status', title: '状态', searchList: {"1": '启用', "0": '禁用'}, formatter: Table.api.formatter.toggle},
						{field: 'create_time', title: '拉黑时间', formatter: Table.api.formatter.datetime, operate: 'RANGE', addclass: 'datetimerange', sortable: true, defaultValue: Config.default_time},
                        {field: 'update_time', title: __('Updatetime'), formatter: Table.api.formatter.datetime, operate: 'RANGE', addclass: 'datetimerange', sortable: true, visible: false},
                    ]
                ],
                searchFormVisible: true,
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
        api: {
            bindevent: function () {
                Form.api.bindevent($("form[role=form]"));
            }
        }
    };
    return Controller;
});


