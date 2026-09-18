define(['jquery', 'bootstrap', 'backend', 'table', 'form'], function ($, undefined, Backend, Table, Form) {

    var Controller = {
        index: function () {
            // 初始化表格参数配置
            Table.api.init({
                extend: {
                    index_url: 'gameuser/index',
                    add_url: 'gameuser/add',
                    edit_url: 'gameuser/edit',
                    htedit_url: 'gameuser/htedit',
                    coinedit_url: 'gameuser/coinedit',
                    coinimport_url: 'gameuser/coinimport',
                    del_url: 'gameuser/del',
                    multi_url: 'gameuser/multi',
                    table: 'gameuser',
                }
            });

            var table = $("#table");
            var authGroupid = Config.authGroupid && parseInt(Config.authGroupid, 10) === 1;

            // 读取URL中的filter参数（用于从外部链接跳转并筛选）
            var urlSearchParams = new URLSearchParams(window.location.search);
            var urlFilterStr = urlSearchParams.get('filter');

            //在普通搜索渲染后
            table.on('post-common-search.bs.table', function (event, table) {
                var form = $("form", table.$commonsearch);
                $("input[name='agent.name']", form).addClass("selectpage").data("source", "ajax/agentList_source/agent_ids/" + Config.agent_id);
                $("input[name='game.name']", form).addClass("selectpage").data("source", "ajax/gameList_source/agent_ids/" + Config.agent_id);
                Form.events.cxselect(form);
                Form.events.selectpage(form);
            });

            // 初始化表格
            table.bootstrapTable({
                url: $.fn.bootstrapTable.defaults.extend.index_url,
                pk: 'id',
                sortName: 'id',
                queryParams: function(params) {
                    if (urlFilterStr) {
                        // 合并URL中的filter与现有filter，URL filter作为基础
                        if (params.filter && typeof params.filter === 'string' && params.filter !== '{}') {
                            try {
                                var existingFilter = JSON.parse(params.filter);
                                var urlFilterObj = JSON.parse(urlFilterStr);
                                params.filter = JSON.stringify($.extend(urlFilterObj, existingFilter));
                                return params;
                            } catch(e) {}
                        }
                        params.filter = urlFilterStr;
                    }
                    return params;
                },
                columns: [
                    [
                        {checkbox: true},
                        {field: 'id', title: __('Id'), sortable: true},
                        {field: 'image_url', title: '头像', visible: false, events: Table.api.events.image, formatter: Table.api.formatter.images, operate: false},
                        {field: 'username', title: '账号', operate: 'LIKE', formatter:Table.api.formatter.search},
                        {field: 'parent_id', title: '上级Id', visible: false, formatter:Table.api.formatter.search},
                        {field: 'parent_username', title: '上级账号', visible: false, operate: false},
                        {field: 'parent_name', title: '上级昵称', operate: false},
                        // 		{field: 'is_true', title: '内部号', formatter: Table.api.formatter.toggle, custom: {0: 'info', 1:'success'}, searchList: {"0": '否', "1": '是'}},
                        {field: 'game.name', title: '游戏名称', formatter:Table.api.formatter.search, align: 'left'},
                        // 		{field: 'ht_status', title: '代理', formatter: Table.api.formatter.label, custom: {0: 'info', 1:'success'}, searchList: {"0": '否', "1": '是'}},
                        {field: 'vip', title: 'VIP', formatter: Table.api.formatter.label, searchList: {"0": 'V0', "1": 'V1', "2": 'V2'}},
                        {field: 'beishu', title: '倍数', sortable: true, operate: false, visible: authGroupid, switchable: false},
                        {field: 'agent.name', title: '代理商名称', formatter:Table.api.formatter.search, visible: false, operate: 'LIKE', align: 'left'},
                        {field: 'name', title: '昵称', visible: false, operate: 'LIKE', align: 'left', formatter:Table.api.formatter.search},
                        {field: 'receive_name', title: '支付宝姓名', operate: false},
                        {field: 'coin_user', title: '累计金币收益', sortable: true, operate: false,formatter: function (value) {
                                return value*1;
                            }},
                        {field: 'coin_user_month', title: '本月金币收益', operate: false,formatter: function (value) {
                                return value*1;
                            }},
                        {field: 'coin_user_day', title: '今日金币收益', operate: false,formatter: function (value) {
                                return value*1;
                            }},
                        {field: 'coin', title: '可用金币', sortable: true, operate: false,formatter: function (value) {
                                return value*1;
                            }},
                        {field: 'freeze_coin', title: '冻结金币', sortable: true, operate: false,formatter: function (value) {
                                return value*1;
                            }},
                        {field: 'game_addiction_enable', title: '达标', formatter: Table.api.formatter.label, custom: {0: 'info', 1:'success'}, searchList: {"0": '否', "1": '是'}, visible: false, operate: false},
                        {field: 'game_addiction_time', title: '达标时间', visible: false, sortable: true, operate: 'RANGE', addclass: 'datetimerange', operate: false},
                        {field: 'exchange_enable', title: '兑换', visible: false, searchList: {"1": '是', "0": '否'}, formatter: Table.api.formatter.toggle, operate: false},
                        {field: 'is_white', title: '白名单', searchList: {"1": '是', "0": '否'}, formatter: Table.api.formatter.toggle, operate: false},
                        {field: 'status', title: '状态', searchList: {"1": '启用', "0": '禁用'}, formatter: Table.api.formatter.toggle},
                        {field: 'ip_check', title: '注册IP', formatter:Table.api.formatter.search},
                        {field: 'last_login_device_id', title: '最后登陆设备号', visible: false, operate: false},
                        {field: 'last_login_ip', title: '最后登陆IP', formatter:Table.api.formatter.search, visible: false, operate: false},
                        {field: 'last_login_time', title: '最后登陆时间', formatter: Table.api.formatter.datetime, operate: false, addclass: 'datetimerange', sortable: false, visible: false},
                        {field: 'create_time', title: __('Createtime'), formatter: Table.api.formatter.datetime, operate: 'RANGE', addclass: 'datetimerange', sortable: true},
                        {
                            field: 'operate', title: __('Operate'), table: table,
                            events: Table.api.events.operate,
                            buttons: [
                                {
                                    name: 'htedit',
                                    title: '改绑关系',
                                    text: '改绑关系',
                                    icon: '',
                                    classname: 'btn btn-warning btn-xs btn-detail btn-dialog',
                                    url: 'gameuser/htedit',
                                },
                                //                         {
                                // 	name: 'duozh',
                                // 	title: '多账号',
                                // 	text: '多账号',
                                // 	icon: '',
                                // 	classname: 'btn btn-info btn-xs btn-detail btn-dialog',
                                // 	url: 'users/duozh/index/user_id/{ids}',
                                // 	extend: 'data-area=\'["80%","80%"]\'',
                                // },
                                {
                                    name: 'yige',
                                    title: '单APP行为',
                                    text: '单APP行为',
                                    icon: '',
                                    classname: 'btn btn-success btn-xs btn-detail btn-dialog',
                                    url: 'users/yige/index/user_id/{ids}',
                                    extend: 'data-area=\'["80%","80%"]\'',
                                },
                                // {
                                // 	name: 'duoge',
                                // 	title: '多APP行为',
                                // 	text: '多APP行为',
                                // 	icon: '',
                                // 	classname: 'btn btn-info btn-xs btn-detail btn-dialog',
                                // 	url: 'users/duoge/index/user_id/{ids}',
                                // 	extend: 'data-area=\'["80%","80%"]\'',
                                // },
                                {
                                    name: 'coinedit',
                                    title: '修改金币',
                                    text: '修改金币',
                                    icon: '',
                                    classname: 'btn btn-warning btn-xs btn-detail btn-dialog',
                                    url: 'gameuser/coinedit',
                                },

                            ],
                            formatter: Table.api.formatter.operate
                        }
                    ]
                ],
                searchFormVisible: true,
                pagination: true,
                search: false,
                commonSearch: true,
            });

            // 清空金币
            $(document).on('click', '.btn-coinclear', function () {
                var ids = Table.api.selectedids(table);
                Layer.confirm(__('确认清空金币吗', ids.length),
                    {icon: 3, title: __('Warning'), offset: 0, shadeClose: true, btn: [__('OK'), __('Cancel')]},
                    function (index) {
                        Fast.api.ajax({
                            url: "gameuser/coinclear",
                            type: "post",
                            data: {ids: ids},
                        }, function () {
                            table.bootstrapTable('refresh', {});
                        });
                        Layer.close(index);
                    }
                );
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
        htedit: function () {
            Controller.api.bindevent();
        },
        coinedit: function () {
            Controller.api.bindevent();
        },
        coinimport: function () {
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


