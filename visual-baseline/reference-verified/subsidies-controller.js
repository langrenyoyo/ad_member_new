define(['jquery', 'bootstrap', 'backend', 'table', 'form'], function ($, undefined, Backend, Table, Form) {

    var Controller = {
        index: function () {

            // 初始化表格参数配置
            Table.api.init({
                extend: {
                    index_url: 'butie/index',
                    edit_url: 'butie/edit',
                    del_url: 'butie/del',
                    multi_url: 'butie/multi',
                    table: 'butie',
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
                        {checkbox: true},
                        {field: 'id', title: __('Id'), operate: false, sortable: true},
						{field: 'user_id', title: '会员ID', formatter:Table.api.formatter.search},
						{field: 'user.username', title: '账号', operate: 'LIKE', formatter:Table.api.formatter.search},
						{field: 'user.vip', title: 'VIP', formatter: Table.api.formatter.label, searchList: {"0": 'V0', "1": 'V1', "2": 'V2'}},
						{field: 'user.parent_id', title: '上级Id', visible: false, formatter:Table.api.formatter.search},
						{field: 'user.parent_username', title: '上级账号', visible: false, operate: false},
						{field: 'user.parent_name', title: '上级昵称', operate: false},
						{field: 'game.name', title: '游戏名称', align: 'left', formatter:Table.api.formatter.search},
						{field: 'agent.name', title: '代理商名称', operate: 'LIKE', visible: false, align: 'left', formatter:Table.api.formatter.search},
						{field: 'user.name', title: '昵称', visible: false, operate: 'LIKE', align: 'left', formatter:Table.api.formatter.search},
						
						{field: 'tx_price', title: '提现金额条件(元)', sortable: true, operate: false,formatter: function (value) {
                            return value*1;
                        }},
						{field: 'pics', title: '申请图片', events: Table.api.events.image, formatter: Table.api.formatter.images},
                        
						{field: 'receive_name', title: '收件人', formatter:Table.api.formatter.search},
						{field: 'receive_tel', title: '联系方式', formatter:Table.api.formatter.search},
						{field: 'price', title: '到账金额(元)', sortable: true, operate: false,formatter: function (value) {
                            return value*1;
                        }},
                        
                        {
							field: 'buttons',
							width: "120px",
							title: '用户行为',
							table: table,
							events: Table.api.events.operate,
							buttons: [
								{
									name: 'yige',
									title: '单APP行为',
									text: '单APP行为',
									icon: '',
									classname: 'btn btn-success btn-xs btn-detail btn-dialog',
									//url: 'users/yige/index/user_id/{ids}',
									url: function (row){
										return 'users/yige/index/user_id/' + row.user.id;
									},
									extend: 'data-area=\'["80%","80%"]\'',
								}
							],
							operate: false,
							formatter:function (value, row, index) {
								var that = $.extend({}, this);
								var table = $(that.table).clone(true);
								$(table).data("operate-edit", null);
								$(table).data("operate-del", null);
								that.table = table;
								return Table.api.formatter.operate.call(that, value, row, index);
                            },
						},
					
						{field: 'status', title: '状态', formatter: Table.api.formatter.label, custom: {0: 'info', 1:'primary', 4:'danger'}, searchList: {"0": '申请中', "1": '审核通过', "4": '审核失败',}},
						{field: 'sub_msg', title: '失败原因', operate: false, align: 'left'},
						{
                            field: 'operate', title: __('Operate'), table: table,
                            events: Table.api.events.operate,
                            buttons: [
								
							],
                            formatter:function (value, row, index) {
								var that = $.extend({}, this);
								var table = $(that.table).clone(true);
								
                                if (row.status == 1 || row.status == 4) {
								//	$(table).data("operate-edit", null);
                                }
								that.table = table;
								return Table.api.formatter.operate.call(that, value, row, index);
                            },
                        },
						
						{field: 'create_time', title: '申请时间', formatter: Table.api.formatter.datetime, operate: 'RANGE', addclass: 'datetimerange', sortable: true, defaultValue: Config.default_time},
                        {field: 'update_time', title: __('Updatetime'), formatter: Table.api.formatter.datetime, operate: 'RANGE', addclass: 'datetimerange', sortable: true, visible: false},
                        
                    ]
                ],
                searchFormVisible: true,
                pagination: true,
                search: false,
                commonSearch: true,
            });

            $(document).on('click', '.btn-agree', function () {
				var ids = Table.api.selectedids(table);
				Layer.confirm(__('确认批量同意吗', ids.length),
					{icon: 3, title: __('Warning'), offset: 0, shadeClose: true, btn: [__('OK'), __('Cancel')]},
					function (index) {
						Fast.api.ajax({
							url: "butie/agree",
							type: "post",
							data: {ids: ids},
						}, function () {
							table.bootstrapTable('refresh', {});
						});
						Layer.close(index);
					}
				);
            });
			$(document).on('click', '.btn-refuse', function () {
				var ids = Table.api.selectedids(table);
				Layer.confirm(__('确认批量拒绝吗', ids.length),
					{icon: 3, title: __('Warning'), offset: 0, shadeClose: true, btn: [__('OK'), __('Cancel')]},
					function (index) {
						Fast.api.ajax({
							url: "butie/refuse",
							type: "post",
							data: {ids: ids},
						}, function () {
							table.bootstrapTable('refresh', {});
						});
						Layer.close(index);
					}
				);
            });
			
            //当表格数据加载完成时
            table.on('load-success.bs.table', function (e, data) {
                $("#tixian1").text(data.extend.tixian1);
                $("#tixian2").text(data.extend.tixian2);
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


