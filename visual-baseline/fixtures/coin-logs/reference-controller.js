define(['jquery', 'bootstrap', 'backend', 'table', 'form'], function ($, undefined, Backend, Table, Form) {

    var Controller = {
        index: function () {
            // 初始化表格参数配置
            Table.api.init({
                extend: {
                    index_url: 'profit/coinlog/index',
                    table: 'profit_coinlog',
                }
            });
				
            var table = $("#table");
			
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
                columns: [
                    [
                        /* {checkbox: true}, */
                        {field: 'id', title: __('Id'), operate: false},
						{field: 'user_id', title: '会员ID', formatter:Table.api.formatter.search},
						{field: 'user.username', title: '用户账号', operate: 'LIKE', formatter:Table.api.formatter.search},
						{field: 'game.name', title: '游戏名称', align: 'left', formatter:Table.api.formatter.search},
						{field: 'agent.game_ad_status', title: '广告状态', visible: false, formatter: Table.api.formatter.label, searchList: {"0": '正常', "1": '封禁'}, custom: {0: 'success', 1:'danger'}, defaultValue: 0},
						{field: 'agent.name', title: '代理商名称', operate: 'LIKE', align: 'left', formatter:Table.api.formatter.search},
						{field: 'coin_before', title: '金币变动前', sortable: true, operate: false,formatter: function (value) {
                            return value*1;
                        }},
						{field: 'coin', title: '金币变动', sortable: true, operate: false,formatter: function (value) {
                            return value*1;
                        }},
						{field: 'coin_after', title: '金币变动后', sortable: true, operate: false,formatter: function (value) {
                            return value*1 ;
                        }},
						{field: 'type', title: '类型', formatter: Table.api.formatter.label, custom: {100: 'info', 10:'success', 30:'warning', 40:'danger', 50:'info', 60:'primary', 70:'success'}, searchList: {"100": '后台', "10": '抽奖', "30": '兑换', "40": '分销', "50": '签到', "60": 'VIP', "70": '任务', "80": '其它'}},
						{field: 'remark', title: '备注', operate: 'LIKE'},
                        {field: 'create_time', title: __('Createtime'), formatter: Table.api.formatter.datetime, operate: 'RANGE', addclass: 'datetimerange', sortable: true, defaultValue: Config.default_time}
                    ]
                ],
				searchFormVisible: true,
                pagination: true,
                search: false,
                commonSearch: true,
            });
			
			//当表格数据加载完成时
            table.on('load-success.bs.table', function (e, data) {
                $("#coin").text(data.extend.coin);
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


