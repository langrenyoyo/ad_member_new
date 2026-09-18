define(['jquery', 'bootstrap', 'backend', 'table', 'form'], function ($, undefined, Backend, Table, Form) {

    var Controller = {
        index: function () {
			var user_id=Fast.api.query('user_id');
			
            // 初始化表格参数配置
            Table.api.init();

            //绑定事件
            $('a[data-toggle="tab"]').on('shown.bs.tab', function (e) {
                var panel = $($(this).attr("href"));
                if (panel.size() > 0) {
                    Controller.table[panel.attr("id")].call(this);
                    $(this).on('click', function (e) {
                        $($(this).attr("href")).find(".btn-refresh").trigger("click");
                    });
                }
                //移除绑定的事件
                $(this).unbind('shown.bs.tab');
            });

            //必须默认触发shown.bs.tab事件
            $('ul.nav-tabs li.active a[data-toggle="tab"]').trigger("shown.bs.tab");
        },
        table: {
            first: function () {
                // 表格1
                var table1 = $("#table1");
				var user_id=Fast.api.query('user_id');
				
                table1.bootstrapTable({
                    url: 'users/lottery/index/user_id/' + user_id + '/type/1',
                    toolbar: '#toolbar1',
                    sortName: 'id',
                    search: false,
                    columns: [
                        [
                            {field: 'id', title: __('Id'), operate: false},
							{field: 'user_id', title: '会员ID', formatter:Table.api.formatter.search},
							{field: 'user.username', title: '用户账号', operate: 'LIKE', operate: false},
							{field: 'game.name', title: '游戏名称', operate: 'LIKE', align: 'left', formatter:Table.api.formatter.search},
							{field: 'lottery_price', title: '金币', sortable: true, operate: false,formatter: function (value) {
								return value*1;
							}},
							{field: 'ecpm', title: 'ECPM', operate: false},
							{field: 'adn_name', title: '类型'},
							{field: 'ip', title: '公网IP', formatter:Table.api.formatter.search},
							{field: 'network_status', title: '内网', searchList: {"1": '否', "0": '是'}, custom: {0: 'warning', 1:'success'}, formatter: Table.api.formatter.label},
							{field: 'tag', title: '是否风控', operate: 'LIKE', align: 'left', operate: false},
							{field: 'user.is_white', title: '白名单', searchList: {"1": '是', "0": '否'}, formatter: Table.api.formatter.label},
							{field: 'status', title: '状态', formatter: Table.api.formatter.label, custom: {0: 'danger', 1:'success'}, searchList: {"0": '失败', "1": '成功'}},
							{field: 'create_time', title: '抽奖时间', formatter: Table.api.formatter.datetime, operate: 'RANGE', addclass: 'datetimerange', sortable: true},
							{field: 'ad_network_rit_id', title: '广告代码位', operate: false},
							{field: 'request_id', title: '广告request_id', operate: false},
							{field: 'trans_id', title: '交易trans_id', operate: false},
                        ]
                    ]
                });

                // 为表格1绑定事件
                Table.api.bindevent(table1);
            },
            second: function () {
                // 表格2
                var table2 = $("#table2");
				var user_id=Fast.api.query('user_id');
                table2.bootstrapTable({
                    url: 'users/risk/index/user_id/' + user_id + '/type/1',
                    toolbar: '#toolbar2',
                    sortName: 'id',
                    search: false,
                    columns: [
                        [
                            {field: 'id', title: __('Id'), operate: false},
							{field: 'user.username', title: '用户账号', operate: 'LIKE', operate: false},
							{field: 'game.name', title: '游戏名称', operate: 'LIKE', align: 'left', formatter:Table.api.formatter.search},
							{field: 'ip', title: 'ip', formatter:Table.api.formatter.search},
							{field: 'network_status', title: '内网', searchList: {"1": '否', "0": '是'}, custom: {0: 'warning', 1:'success'}, formatter: Table.api.formatter.label},
							{field: 'tag', title: '标签'},
							{field: 'create_time', title: __('Createtime'), formatter: Table.api.formatter.datetime, operate: 'RANGE', addclass: 'datetimerange', sortable: true}
                        ]
                    ]
                });

                // 为表格2绑定事件
                Table.api.bindevent(table2);
            },
			third: function () {
                // 表格3
                var table3 = $("#table3");
				var user_id=Fast.api.query('user_id');
                table3.bootstrapTable({
                    url: 'users/coinday/index/user_id/' + user_id + '/type/1',
                    toolbar: '#toolbar3',
                    sortName: 'id',
                    search: false,
                    columns: [
                        [
                            {field: 'id', title: __('Id'), operate: false},
							{field: 'user_id', title: '会员ID', formatter:Table.api.formatter.search},
							{field: 'user.username', title: '用户账号', operate: 'LIKE', operate: false},
							{field: 'game.name', title: '游戏名称', operate: 'LIKE', align: 'left', formatter:Table.api.formatter.search},
							{field: 'coin', title: '收益', sortable: true, operate: false,formatter: function (value) {
								return value*1;
							}},
							{field: 'date', title: '时间', formatter: Table.api.formatter.date, operate: 'RANGE', addclass: 'datetimerange', sortable: true}
                        ]
                    ]
                });

                // 为表格3绑定事件
                Table.api.bindevent(table3);
            },
			four: function () {
                // 表格4
                var table4 = $("#table4");
				var user_id=Fast.api.query('user_id');
                table4.bootstrapTable({
                    url: 'users/coinlog/index/user_id/' + user_id + '/type/1',
                    toolbar: '#toolbar4',
                    sortName: 'id',
                    search: false,
                    columns: [
                        [
                            {field: 'id', title: __('Id'), operate: false},
							{field: 'user_id', title: '会员ID', formatter:Table.api.formatter.search},
							{field: 'user.username', title: '用户账号', operate: 'LIKE', operate: false},
							{field: 'game.name', title: '游戏名称', operate: 'LIKE', align: 'left', formatter:Table.api.formatter.search},
							{field: 'coin_before', title: '金币变动前', sortable: true, operate: false,formatter: function (value) {
								return value*1;
							}},
							{field: 'coin', title: '金币变动', sortable: true, operate: false,formatter: function (value) {
								return value*1;
							}},
							{field: 'coin_after', title: '金币变动后', sortable: true, operate: false,formatter: function (value) {
								return value*1;
							}},
							{field: 'type', title: '类型', formatter: Table.api.formatter.label, custom: {100: 'info', 10:'success', 30:'warning', 40:'danger', 50:'info'}, searchList: {"100": '后台', "10": '抽奖', "30": '兑换', "40": '分销', "50": '签到'}},
							{field: 'remark', title: '备注', operate: 'LIKE'},
							{field: 'create_time', title: __('Createtime'), formatter: Table.api.formatter.datetime, operate: 'RANGE', addclass: 'datetimerange', sortable: true}
                        ]
                    ]
                });
				
				table4.on('load-success.bs.table', function (e, data) {
					//这里我们手动设置底部的值
					$("#coin_toolbar4").text(data.extend.coin);
				});
				
                // 为表格4绑定事件
                Table.api.bindevent(table4);
            },
			five: function () {
                // 表格5
                var table5 = $("#table5");
				var user_id=Fast.api.query('user_id');
                table5.bootstrapTable({
					url: 'users/exchange/index/user_id/' + user_id + '/type/1',
					extend: {
                        edit_url: 'tixian/edit',
                    },
                    toolbar: '#toolbar5',
                    sortName: 'id',
                    search: false,
                    columns: [
                        [
							{checkbox: true},
							{field: 'id', title: __('Id'), operate: false},
							{field: 'user_id', title: '会员ID', formatter:Table.api.formatter.search},
							{field: 'user.username', title: '账号', operate: false},
							{field: 'game.name', title: '游戏名称', operate: 'LIKE', align: 'left', formatter:Table.api.formatter.search},
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
							{field: 'receive_name', title: '收件人', formatter:Table.api.formatter.search},
							{field: 'receive_tel', title: '联系方式', formatter:Table.api.formatter.search},
							{field: 'receive_address', title: '收货地址', visible: false, operate: false, align: 'left'},
							{field: 'delivery_name', title: '快递名称', visible: false, operate: false},
							{field: 'delivery_no', title: '快递单号', visible: false, operate: false},
							{field: 'remark', title: '备注', visible: false, operate: false},
							/* {field: 'status', title: '状态', formatter: Table.api.formatter.label, custom: {0: 'info', 1:'success', 2:'warning', 3:'success', 4:'danger'}, searchList: {"0": '申请中', "1": '审核通过', "2": '已发货', "3": '已收货', "4": '审核失败'}}, */
							{field: 'status', title: '状态', formatter: Table.api.formatter.label, custom: {0: 'info', 1:'success', 4:'danger'}, searchList: {"0": '申请中', "1": '审核通过', "4": '审核失败'}},
							{field: 'reason', title: '拒绝原因', visible: false, operate: false, align: 'left'},
							{field: 'operate', title: __('Operate'), table: table5,
								events: Table.api.events.operate,
								buttons: [
									{
										name: 'agree',
										title: '同意',
										text: '同意',
										icon: '',
										classname: 'btn btn-primary btn-xs btn-detail btn-ajax',
										url: 'tixian/agreeorrefuse/ids/{ids}/status/1',
										confirm: '确认同意吗',
										success: function (data, ret) {
											table5.bootstrapTable('refresh', {});
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
											table5.bootstrapTable('refresh', {});
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
									if (row.status == 1 || row.status == 4) {
										$(table).data("operate-edit", null);
									}
									that.table = table;
									return Table.api.formatter.operate.call(that, value, row, index);
								},
							},
							{field: 'create_time', title: '申请时间', formatter: Table.api.formatter.datetime, operate: 'RANGE', addclass: 'datetimerange', sortable: true},
							{field: 'update_time', title: __('Updatetime'), formatter: Table.api.formatter.datetime, operate: 'RANGE', addclass: 'datetimerange', sortable: true, visible: false},
                        ]
                    ]
                });

				$(document).on('click', '.btn-agree', function () {
					var ids = Table.api.selectedids(table5);
					Layer.confirm(__('确认批量同意吗', ids.length),
						{icon: 3, title: __('Warning'), offset: 0, shadeClose: true, btn: [__('OK'), __('Cancel')]},
						function (index) {
							Fast.api.ajax({
								url: "tixian/agree",
								type: "post",
								data: {ids: ids},
							}, function () {
								table5.bootstrapTable('refresh', {});
							});
							Layer.close(index);
						}
					);
				});
				$(document).on('click', '.btn-refuse', function () {
					var ids = Table.api.selectedids(table5);
					Layer.confirm(__('确认批量拒绝吗', ids.length),
						{icon: 3, title: __('Warning'), offset: 0, shadeClose: true, btn: [__('OK'), __('Cancel')]},
						function (index) {
							Fast.api.ajax({
								url: "tixian/refuse",
								type: "post",
								data: {ids: ids},
							}, function () {
								table5.bootstrapTable('refresh', {});
							});
							Layer.close(index);
						}
					);
				});
				
                // 为表格5绑定事件
                Table.api.bindevent(table5);
            },
			six: function () {
                // 表格6
                var table6 = $("#table6");
				var user_id=Fast.api.query('user_id');
                table6.bootstrapTable({
                    url: 'users/distribution/index/user_id/' + user_id + '/type/1',
                    toolbar: '#toolbar6',
                    sortName: 'id',
                    search: false,
                    columns: [
                        [
                            {field: 'id', title: __('Id'), operate: false},
							{field: 'username', title: '账号', operate: 'LIKE'},
							{field: 'game.name', title: '游戏名称', operate: 'LIKE', align: 'left', formatter:Table.api.formatter.search},
							{field: 'coin_user', title: '累计金币收益', sortable: true, operate: false,formatter: function (value) {
								return value*1;
							}},
							{field: 'coin', title: '可用金币', sortable: true, operate: false,formatter: function (value) {
								return value*1;
							}},
							{field: 'freeze_coin', title: '冻结金币', sortable: true, operate: false,formatter: function (value) {
								return value*1;
							}},
							{field: 'is_white', title: '白名单', formatter: Table.api.formatter.label, custom: {1:'success', 0:'warning'}, searchList: {"1": '是', "0": '否'}},
							{field: 'status', title: '状态', formatter: Table.api.formatter.label, custom: {1:'success', 0:'warning'}, searchList: {"1": '正常', "0": '禁用'}},
							{field: 'create_time', title: __('Createtime'), formatter: Table.api.formatter.datetime, operate: 'RANGE', addclass: 'datetimerange', sortable: true}
                        ]
                    ]
                });

                // 为表格6绑定事件
                Table.api.bindevent(table6);
            },
			seven: function () {
                // 表格7
                var table7 = $("#table7");
				var user_id=Fast.api.query('user_id');
                table7.bootstrapTable({
                    url: 'users/loginlog/index/user_id/' + user_id + '/type/1',
                    toolbar: '#toolbar7',
                    sortName: 'id',
                    search: false,
                    columns: [
                        [
                            {field: 'id', title: __('Id'), operate: false},
							{field: 'user_id', title: '会员ID', formatter:Table.api.formatter.search},
							{field: 'user.username', title: '用户账号', operate: 'LIKE', operate: false},
							{field: 'game.name', title: '游戏名称', align: 'left', formatter:Table.api.formatter.search},
							{field: 'device_id', title: '设备号', operate: false},
							{field: 'ip', title: 'IP', formatter:Table.api.formatter.search},
							{field: 'create_time', title: '登陆时间', formatter: Table.api.formatter.datetime, operate: 'RANGE', addclass: 'datetimerange', sortable: true}
                        ]
                    ]
                });

                // 为表格7绑定事件
                Table.api.bindevent(table7);
            },
			eight: function () {
                // 表格8
                var table8 = $("#table8");
				var user_id=Fast.api.query('user_id');
                table8.bootstrapTable({
                    url: 'users/address/index/user_id/' + user_id + '/type/1',
                    toolbar: '#toolbar8',
                    sortName: 'id',
                    search: false,
                    columns: [
                        [
                            {field: 'id', title: __('Id'), operate: false},
							{field: 'user_id', title: '会员ID', formatter:Table.api.formatter.search},
							{field: 'user.username', title: '用户账号', operate: false},
							{field: 'game.name', title: '游戏名称', align: 'left', formatter:Table.api.formatter.search},
							{field: 'receive_name', title: '收件人'},
							{field: 'receive_tel', title: '联系方式'},
							{field: 'receive_postcode', title: '邮箱编号'},
							{field: 'receive_address', title: '详细地址'},
							{field: 'default_status', title: '默认地址', formatter: Table.api.formatter.label, searchList: {"1": '是', "0": '否'}, operate: false},
							{field: 'create_time', title: __('Createtime'), formatter: Table.api.formatter.datetime, operate: 'RANGE', addclass: 'datetimerange', sortable: true}
                        ]
                    ]
                });

                // 为表格8绑定事件
                Table.api.bindevent(table8);
            },
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
            },
        }
    };
    return Controller;
});