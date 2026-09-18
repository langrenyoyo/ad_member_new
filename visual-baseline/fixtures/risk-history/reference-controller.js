define(['jquery', 'bootstrap', 'backend', 'table', 'form'], function ($, undefined, Backend, Table, Form) {

    var Controller = {
        index: function () {
            // 初始化表格参数配置
            Table.api.init({
                extend: {
                    index_url: 'risk/risk/index',
                    table: 'risk_risk',
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
                        {field: 'user_id', title: '会员ID', operate: 'LIKE', formatter:Table.api.formatter.search},
						{field: 'user.username', title: '用户账号', operate: 'LIKE', formatter:Table.api.formatter.search},
						{field: 'user.parent_id', title: '上级Id', visible: false, formatter:Table.api.formatter.search},
						{field: 'game.name', title: '游戏名称', align: 'left', formatter:Table.api.formatter.search},
						{field: 'agent.name', title: '代理商名称', operate: 'LIKE', visible: false, align: 'left', formatter:Table.api.formatter.search},
						{field: 'tagcode', title: '标签', operate: 'LIKE'},
						{field: 'tags', title: '标签名', operate: false},
						{field: 'hardware_main_id', title: '硬件主ID', operate: 'LIKE', align: 'left', formatter:Table.api.formatter.search},
						{field: 'ip', title: 'ip', formatter:Table.api.formatter.search},
						{field: 'action', title: '行为', operate: false},
						{field: 'risk_score', title: '风险分数', operate: false},
						{field: 'risk_level', title: '风险等级', operate: false},
                        {field: 'create_time', title: __('Createtime'), formatter: Table.api.formatter.datetime, operate: 'RANGE', addclass: 'datetimerange', sortable: true}
                    ]
                ],
                searchFormVisible: true,
                pagination: true,
                search: false,
                commonSearch: true,
            });
			
            // 为表格绑定事件
            Table.api.bindevent(table);
			
			// 指定搜索条件
            $(document).on("click", ".btn-singlesearch", function () {
                var options = table.bootstrapTable('getOptions');
                var queryParams = options.queryParams;
                options.pageNumber = 1;
                options.queryParams = function (params) {
                    //这一行必须要存在,否则在点击下一页时会丢失搜索栏数据
                    params = queryParams(params);

                    //如果希望追加搜索条件,可使用
                    var filter = params.filter ? JSON.parse(params.filter) : {};
                    var op = params.op ? JSON.parse(params.op) : {};
                    filter.usernameMulti = '1';
                    op.usernameMulti = '1';

                    params.filter = JSON.stringify(filter);
                    params.op = JSON.stringify(op);

                    //如果希望忽略搜索栏搜索条件,可使用
                    //params.filter = JSON.stringify({url: 'login'});
                    //params.op = JSON.stringify({url: 'like'});
                    return params;
                };
                table.bootstrapTable('refresh', {});
                //Toastr.info("当前执行的是自定义搜索,搜索URL中包含login的数据");
                return false;
            });
			
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


