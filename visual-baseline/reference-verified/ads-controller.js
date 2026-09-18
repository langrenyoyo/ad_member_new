define(['jquery', 'bootstrap', 'backend', 'table', 'form'], function ($, undefined, Backend, Table, Form) {

    var Controller = {
        index: function () {
			
            // 初始化表格参数配置
            Table.api.init({
                extend: {
                    index_url: 'ad/index',
                    table: 'ad',
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
						{field: 'id', title: __('Id'), operate: false},
						{field: 'user.parent_id', title: '上级Id', formatter:Table.api.formatter.search},
						{field: 'receive_name_parent', title: '上级支付宝姓名', operate: false},
						{field: 'user_id', title: '会员ID', formatter:Table.api.formatter.search},
						{field: 'user.username', title: '用户账号', operate: 'LIKE', formatter:Table.api.formatter.search, operate: false},
						{field: 'receive_name', title: '支付宝姓名', operate: false},
						{field: 'game.name', title: '游戏名称', align: 'left', formatter:Table.api.formatter.search},
						{field: 'agent.name', title: '代理商名称', visible: false, operate: 'LIKE', align: 'left', formatter:Table.api.formatter.search},
						{field: 'pre_ecpm', title: 'ECPM', sortable: true, operate: false},
						{field: 'estimate_income', title: '金币', sortable: true, operate: 'BETWEEN',formatter: function (value) {
							return value*1;
						}},
						{field: 'ad_network_platform_name', title: '广告平台', sortable: true},
						{field: 'is_lottery', title: '抽奖', formatter: Table.api.formatter.label, custom: {0: 'info', 1:'success'}, searchList: {"0": '否', "1": '是'}, operate: false},
						{field: 'is_rw', title: '任务', formatter: Table.api.formatter.label, custom: {0: 'info', 1:'success'}, searchList: {"0": '否', "1": '是'}, operate: false},
						{field: 'is_type', title: '奖励类型', searchList: {"1": '领取', "0": '提升'}, formatter: Table.api.formatter.label, operate: false},
						{field: 'is_fu', title: '广告类型', searchList: {"1": '副广', "0": '激励'}, formatter: Table.api.formatter.label, defaultValue: 0},
						{field: 'fu_type', title: '副广类型', searchList: {"1": '开屏', "2": 'Banner', "3": '插屏', "4": '信息流'}, custom: {1: 'info', 2:'success', 3:'warning', 4:'danger'}, formatter: Table.api.formatter.label},
						{field: 'is_look', title: '状态', formatter: Table.api.formatter.label, custom: {0: 'info', 1:'success'}, searchList: {"0": '失败', "1": '成功'}},
						{field: 'create_time', title: '观看时间', formatter: Table.api.formatter.datetime, operate: 'RANGE', addclass: 'datetimerange', sortable: true, defaultValue: Config.default_time},
						{field: 'ad_network_rit_id', title: '广告代码位', operate: false},
						{field: 'request_id', title: '广告request_id', operate: false, sortable: true},
						{field: 'trans_id', title: '交易trans_id', operate: false},
					]
				],
				searchFormVisible: true,
                pagination: true,
                search: false,
                commonSearch: true,
            });
            
            //当表格数据加载完成时
            table.on('load-success.bs.table', function (e, data) {
                $("#money1").text(data.extend.money1);
                $("#money2").text(data.extend.money2);
                $("#tixian1").text(data.extend.tixian1);
                $("#tixian2").text(data.extend.tixian2);
            });
			
			$(".btn-export").click(function(){
				var options = table.bootstrapTable('getOptions');
				var search = options.queryParams({});
				var filter = search.filter;
				var op = search.op;
				window.location.href = 'ad/export' + '?filter=' + filter + '&op=' + op;
			})
			
            // 为表格绑定事件
            Table.api.bindevent(table);
        },
        add: function () {
            Controller.api.bindevent();
        },
        edit: function () {
            Controller.api.bindevent();
        },
		reason: function () {
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


