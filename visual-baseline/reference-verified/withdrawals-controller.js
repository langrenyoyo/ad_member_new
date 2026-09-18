define(['jquery', 'bootstrap', 'backend', 'table', 'form'], function ($, undefined, Backend, Table, Form) {

    var Controller = {
        index: function () {

            // 初始化表格参数配置
            Table.api.init({
                extend: {
                    index_url: 'tixian/index',
                    edit_url: 'tixian/edit',
                    del_url: 'tixian/del',
                    multi_url: 'tixian/multi',
                    reason_url: 'tixian/reason',
                    table: 'tixian',
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
				// 		{field: 'user.ht_status', title: '代理', formatter: Table.api.formatter.label, custom: {0: 'info', 1:'success'}, searchList: {"0": '否', "1": '是'}},
						{field: 'user.vip', title: 'VIP', formatter: Table.api.formatter.label, searchList: {"0": 'V0', "1": 'V1', "2": 'V2'}},
						{field: 'user.parent_id', title: '上级Id', visible: false, formatter:Table.api.formatter.search},
						{field: 'user.parent_username', title: '上级账号', visible: false, operate: false},
						{field: 'user.parent_name', title: '上级昵称', operate: false},
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
						{field: 'game.name', title: '游戏名称', align: 'left', formatter:Table.api.formatter.search},
						{field: 'agent.name', title: '代理商名称', operate: 'LIKE', visible: false, align: 'left', formatter:Table.api.formatter.search},
						{field: 'user.name', title: '昵称', visible: false, operate: 'LIKE', align: 'left', formatter:Table.api.formatter.search},
						{field: 'good.name', title: '商品名称', operate: 'LIKE', align: 'left'},
						/* {field: 'receive_number', title: '数量', visible: false, operate: false,formatter: function (value) {
                            return value*1;
                        }},
						{field: 'exchange_value', title: '兑换金币', visible: false, sortable: true, operate: false,formatter: function (value) {
                            return value*1;
                        }}, */
						{field: 'exchange_value', title: '金额', sortable: true, operate: false,formatter: function (value) {
                            return value*1/10 + '元';
                        }},
                        {field: 'device_manufacturer', title: '手机型号', operate: false, align: 'left'},
						{field: 'receive_name', title: '收件人', formatter:Table.api.formatter.search},
						{field: 'receive_tel', title: '联系方式', formatter:Table.api.formatter.search},
						{field: 'receive_address', title: '收货地址', visible: false, operate: false, align: 'left'},
						{field: 'delivery_name', title: '快递名称', visible: false, operate: false},
						{field: 'delivery_no', title: '快递单号', visible: false, operate: false},
						{field: 'remark', title: '备注', visible: false, operate: false},
						{field: 'exchange_type', title: '提现方式', formatter: Table.api.formatter.label, custom: {0:'info', 1:'primary', 2:'danger'}, searchList: {"0": '默认', "1": '支付宝', "2": '微信'}},
						/* {field: 'status', title: '状态', formatter: Table.api.formatter.label, custom: {0: 'info', 1:'primary', 2:'warning', 3:'success', 4:'danger'}, searchList: {"0": '申请中', "1": '审核通过', "2": '已发货', "3": '已收货', "4": '审核失败',}}, */
						{field: 'user.is_true', title: '内部号', formatter: Table.api.formatter.label, custom: {0: 'info', 1:'success'}, searchList: {"0": '否', "1": '是'}, visible: false, operate: false},
						{field: 'status', title: '状态', formatter: Table.api.formatter.label, custom: {0: 'info', 1:'primary', 4:'danger'}, searchList: {"0": '申请中', "1": '审核通过', "4": '审核失败',}},
						{field: 'plan_status', title: '定时', formatter: Table.api.formatter.label, custom: {0:'info', 1:'primary', 2:'danger'}, searchList: {"0": '默认', "1": '转账中', "2": '已转账'}},
						{field: 'sub_msg', title: '失败原因', operate: false, align: 'left'},
						{field: 'reason', title: '拒绝原因', visible: false, operate: false, align: 'left'},
						{
                            field: 'operate', title: __('Operate'), table: table,
                            events: Table.api.events.operate,
                            buttons: [
                                {
									name: 'lahei',
									title: '拉黑',
									text: '拉黑',
									icon: '',
									classname: 'btn btn-warning btn-xs btn-detail btn-ajax',
									url: 'tixian/lahei/ids/{ids}',
									confirm: '确认拉黑吗',
									success: function (data, ret) {
                                        table.bootstrapTable('refresh', {});
                                    },
                                    error: function (data, ret) {

                                    }
								},
								{
									name: 'agree',
									title: '同意',
									text: '同意',
									icon: '',
									classname: 'btn btn-primary btn-xs btn-detail btn-ajax',
									url: 'tixian/agreeorrefuse/ids/{ids}/status/1',
									confirm: '确认同意吗',
									success: function (data, ret) {
                                        table.bootstrapTable('refresh', {});
                                    },
                                    error: function (data, ret) {

                                    }
								},
								{
									name: 'refuse',
									title: '拒绝',
									text: '拒绝',
									icon: '',
									classname: 'btn btn-danger btn-xs btn-detail btn-ajax',
									url: 'tixian/agreeorrefuse/ids/{ids}/status/4',
									confirm: '确认拒绝吗',
									success: function (data, ret) {
                                        table.bootstrapTable('refresh', {});
                                    },
                                    error: function (data, ret) {

                                    }
								},
								{
									name: 'reason',
									title: '有理由拒绝',
									text: '有理由拒绝',
									icon: '',
									classname: 'btn btn-danger btn-xs btn-detail btn-dialog',
									url: 'tixian/reason',
								},
							],
                            formatter:function (value, row, index) {
								var that = $.extend({}, this);
								var table = $(that.table).clone(true);
								if (row.status != 0) {
									$(table).data("operate-agree", null);
									$(table).data("operate-refuse", null);
									$(table).data("operate-reason", null);
                                }
                                //if (row.status == 3 || row.status == 4) {
                                if (row.status == 1 || row.status == 4) {
									$(table).data("operate-edit", null);
                                }
								that.table = table;
								return Table.api.formatter.operate.call(that, value, row, index);
                            },
                        },
				// 		{field: 'check_status', title: '作弊审查', formatter: Table.api.formatter.label, custom: {1:'success', 2:'danger', 3:'warning'}, searchList: {"1": '正常', "2": '金币异常', "3": 'ecpm异常', "4": '用户异常', "5": '广告数量异常'}, operate: false},
						{field: 'check_status_txt', title: '作弊审查', operate: false},
						{field: 'create_time', title: '申请时间', formatter: Table.api.formatter.datetime, operate: 'RANGE', addclass: 'datetimerange', sortable: true, defaultValue: Config.default_time},
                        {field: 'update_time', title: __('Updatetime'), formatter: Table.api.formatter.datetime, operate: 'RANGE', addclass: 'datetimerange', sortable: true, visible: false},
                        /* {field: 'operate', title: __('Operate'), table: table, events: Table.api.events.operate, formatter: Table.api.formatter.operate} */
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
							url: "tixian/agree",
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
							url: "tixian/refuse",
							type: "post",
							data: {ids: ids},
						}, function () {
							table.bootstrapTable('refresh', {});
						});
						Layer.close(index);
					}
				);
            });
			$(document).on('click', '.btn-alipay', function () {
				var ids = Table.api.selectedids(table);
				Layer.confirm(__('确认批量支付宝转账(实时)吗', ids.length),
					{icon: 3, title: __('Warning'), offset: 0, shadeClose: true, btn: [__('OK'), __('Cancel')]},
					function (index) {
						Fast.api.ajax({
							url: "tixian/alipay",
							type: "post",
							data: {ids: ids},
						}, function () {
							table.bootstrapTable('refresh', {});
						});
						Layer.close(index);
					}
				);
            });
            $(document).on('click', '.btn-alipay-plan', function () {
				var ids = Table.api.selectedids(table);
				Layer.confirm(__('确认批量支付宝转账(定时)吗', ids.length),
					{icon: 3, title: __('Warning'), offset: 0, shadeClose: true, btn: [__('OK'), __('Cancel')]},
					function (index) {
						Fast.api.ajax({
							url: "tixian/alipay_plan",
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
                $("#tixian3").text(data.extend.tixian3);
            });
            
            $(".btn-export").click(function(){
				var options = table.bootstrapTable('getOptions');
				var search = options.queryParams({});
				var filter = search.filter;
				var op = search.op;
				window.location.href = 'tixian/export' + '?filter=' + filter + '&op=' + op;
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


