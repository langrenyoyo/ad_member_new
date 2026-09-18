define(['jquery', 'bootstrap', 'backend', 'addtabs', 'table', 'form', 'echarts', 'echarts-theme', 'template', 'china'], function ($, undefined, Backend, Datatable, Table, Form, Echarts, undefined, Template) {

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
				var game_id=Fast.api.query('game_id');
				
                table1.bootstrapTable({
                    url: 'games/lottery/index/game_id/' + game_id,
                    toolbar: '#toolbar1',
                    sortName: 'id',
                    search: false,
                    columns: [
                        [
                            {field: 'id', title: __('Id'), operate: false},
							{field: 'user_id', title: '会员ID', formatter:Table.api.formatter.search},
							{field: 'user.username', title: '用户账号', operate: 'LIKE', formatter:Table.api.formatter.search},
							{field: 'game.name', title: '游戏名称', align: 'left', operate: false},
							{field: 'lottery_price', title: '金币', sortable: true, operate: false,formatter: function (value) {
								return value*1;
							}},
							{field: 'ecpm', title: 'ECPM', operate: false},
							{field: 'adn_name', title: '类型'},
							{field: 'ip', title: '公网IP', formatter:Table.api.formatter.search},
							{field: 'network_status', title: '内网', searchList: {"1": '否', "0": '是'}, custom: {0: 'warning', 1:'success'}, formatter: Table.api.formatter.label},
							{field: 'tag', title: '是否风控', operate: 'LIKE', align: 'left', operate: false},
							{field: 'user.is_white', title: '白名单', searchList: {"1": '是', "0": '否'}, formatter: Table.api.formatter.label},
							{field: 'status', title: '状态', formatter: Table.api.formatter.label, custom: {0: 'info', 1:'success'}, searchList: {"0": '失败', "1": '成功'}},
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
				var game_id=Fast.api.query('game_id');
                table2.bootstrapTable({
                    url: 'games/risk/index/game_id/' + game_id,
                    toolbar: '#toolbar2',
                    sortName: 'id',
                    search: false,
                    columns: [
                        [
                            {field: 'id', title: __('Id'), operate: false},
							{field: 'user_id', title: '会员ID', formatter:Table.api.formatter.search},
							{field: 'user.username', title: '用户账号', operate: 'LIKE', formatter:Table.api.formatter.search},
							{field: 'game.name', title: '游戏名称', align: 'left', operate: false},
							{field: 'ip', title: 'ip', formatter:Table.api.formatter.search},
							{field: 'network_status', title: '内网', searchList: {"1": '否', "0": '是'}, custom: {0: 'warning', 1:'success'}, formatter: Table.api.formatter.label},
							{field: 'tag', title: '标签'},
							{field: 'create_time', title: __('Createtime'), formatter: Table.api.formatter.datetime, operate: 'RANGE', addclass: 'datetimerange', sortable: true}
                        ]
                    ]
                });

                // 为表格2绑定事件
                Table.api.bindevent(table2);
				
				// 指定搜索条件
				$(document).on("click", ".btn-singlesearch", function () {
					var options = table2.bootstrapTable('getOptions');
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
					table2.bootstrapTable('refresh', {});
					//Toastr.info("当前执行的是自定义搜索,搜索URL中包含login的数据");
					return false;
				});
            },
			third: function () {
                // 表格3
                var table3 = $("#table3");
				var game_id=Fast.api.query('game_id');
                table3.bootstrapTable({
                    url: 'games/exchange/index/game_id/' + game_id,
					extend: {
                        edit_url: 'tixian/edit',
                    },
                    toolbar: '#toolbar3',
                    sortName: 'id',
                    search: false,
                    columns: [
                        [
                            {checkbox: true},
							{field: 'id', title: __('Id'), operate: false},
							{field: 'user_id', title: '会员ID', formatter:Table.api.formatter.search},
							{field: 'user.username', title: '账号', operate: false},
							{field: 'user.parent_id', title: '上级Id', visible: false, formatter:Table.api.formatter.search},
							{field: 'user.parent_username', title: '上级账号', visible: false, operate: false},
							{field: 'user.parent_name', title: '上级昵称', operate: false},
							{
								field: 'buttons',
								width: "120px",
								title: '用户行为',
								table: table3,
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
							{field: 'game.name', title: '游戏名称', operate: 'LIKE', align: 'left', operate: false},
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
							/* {field: 'status', title: '状态', formatter: Table.api.formatter.label, custom: {0: 'info', 1:'primary', 2:'warning', 3:'success', 4:'danger'}, searchList: {"0": '申请中', "1": '审核通过', "2": '已发货', "3": '已收货', "4": '审核失败',}}, */
							{field: 'user.is_true', title: '内部号', formatter: Table.api.formatter.label, custom: {0: 'info', 1:'success'}, searchList: {"0": '否', "1": '是'}},
							{field: 'status', title: '状态', formatter: Table.api.formatter.label, custom: {0: 'info', 1:'primary', 4:'danger'}, searchList: {"0": '申请中', "1": '审核通过', "4": '审核失败',}},
							{field: 'reason', title: '拒绝原因', visible: false, operate: false, align: 'left'},
							{field: 'operate', title: __('Operate'), table: table3,
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
											table3.bootstrapTable('refresh', {});
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
											table3.bootstrapTable('refresh', {});
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
							{field: 'check_status', title: '作弊审查', formatter: Table.api.formatter.label, custom: {1:'success', 2:'danger', 3:'warning'}, searchList: {"1": '正常', "2": '金币异常', "3": 'ecpm异常'}, operate: false},
							{field: 'create_time', title: '申请时间', formatter: Table.api.formatter.datetime, operate: 'RANGE', addclass: 'datetimerange', sortable: true},
							{field: 'update_time', title: __('Updatetime'), formatter: Table.api.formatter.datetime, operate: 'RANGE', addclass: 'datetimerange', sortable: true, visible: false},
                        ]
                    ]
                });
				
				$(document).on('click', '.btn-agree', function () {
					var ids = Table.api.selectedids(table3);
					Layer.confirm(__('确认批量同意吗', ids.length),
						{icon: 3, title: __('Warning'), offset: 0, shadeClose: true, btn: [__('OK'), __('Cancel')]},
						function (index) {
							Fast.api.ajax({
								url: "tixian/agree",
								type: "post",
								data: {ids: ids},
							}, function () {
								table3.bootstrapTable('refresh', {});
							});
							Layer.close(index);
						}
					);
				});
				$(document).on('click', '.btn-refuse', function () {
					var ids = Table.api.selectedids(table3);
					Layer.confirm(__('确认批量拒绝吗', ids.length),
						{icon: 3, title: __('Warning'), offset: 0, shadeClose: true, btn: [__('OK'), __('Cancel')]},
						function (index) {
							Fast.api.ajax({
								url: "tixian/refuse",
								type: "post",
								data: {ids: ids},
							}, function () {
								table3.bootstrapTable('refresh', {});
							});
							Layer.close(index);
						}
					);
				});

                // 为表格3绑定事件
                Table.api.bindevent(table3);
            },
			four: function () {
                // 表格4
                var table4 = $("#table4");
				var game_id=Fast.api.query('game_id');
                table4.bootstrapTable({
                    url: 'games/user/index/game_id/' + game_id,
					extend: {
						edit_url: 'gameuser/edit',
						coinedit_url: 'gameuser/coinedit',
						del_url: 'gameuser/del',
						multi_url: 'gameuser/multi',
					},
                    toolbar: '#toolbar4',
                    sortName: 'id',
                    search: false,
                    columns: [
                        [
                            {checkbox: true},
							{field: 'id', title: __('Id'), operate: false},
							{field: 'image_url', title: '头像', visible: false, events: Table.api.events.image, formatter: Table.api.formatter.images, operate: false},
							{field: 'username', title: '账号', operate: 'LIKE', formatter:Table.api.formatter.search},
							{field: 'parent_id', title: '上级Id', visible: false, formatter:Table.api.formatter.search},
							{field: 'parent_username', title: '上级账号', visible: false, operate: false},
							{field: 'parent_name', title: '上级昵称', operate: false},
							{field: 'game.name', title: '游戏名称', operate: false, align: 'left'},
							{field: 'name', title: '昵称', visible: false, operate: 'LIKE', align: 'left', formatter:Table.api.formatter.search},
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
							{field: 'is_true', title: '内部号', formatter: Table.api.formatter.label, custom: {0: 'info', 1:'success'}, searchList: {"0": '否', "1": '是'}},
							{field: 'game_addiction_enable', title: '达标', formatter: Table.api.formatter.label, custom: {0: 'info', 1:'success'}, searchList: {"0": '否', "1": '是'}},
							{field: 'game_addiction_time', title: '达标时间', visible: false, sortable: true, operate: 'RANGE', addclass: 'datetimerange'},
							{field: 'exchange_enable', title: '兑换', visible: false, searchList: {"1": '是', "0": '否'}, formatter: Table.api.formatter.toggle},
							{field: 'is_white', title: '白名单', searchList: {"1": '是', "0": '否'}, formatter: Table.api.formatter.toggle},
							{field: 'status', title: '状态', searchList: {"1": '启用', "0": '禁用'}, formatter: Table.api.formatter.toggle},
							{field: 'last_login_device_id', title: '最后登陆设备号', visible: false, operate: false},
							{field: 'last_login_ip', title: '最后登陆IP', formatter:Table.api.formatter.search, visible: false, operate: false},
							{field: 'last_login_time', title: '最后登陆时间', formatter: Table.api.formatter.datetime, operate: false, addclass: 'datetimerange', sortable: false, visible: false},
							{field: 'create_time', title: __('Createtime'), formatter: Table.api.formatter.datetime, operate: 'RANGE', addclass: 'datetimerange', sortable: true},
							{
								field: 'operate', title: __('Operate'), table: table4,
								events: Table.api.events.operate,
								buttons: [
									{
										name: 'yige',
										title: '单APP行为',
										text: '单APP行为',
										icon: '',
										classname: 'btn btn-success btn-xs btn-detail btn-dialog',
										url: 'users/yige/index/user_id/{ids}',
										extend: 'data-area=\'["80%","80%"]\'',
									},
									{
										name: 'duoge',
										title: '多APP行为',
										text: '多APP行为',
										icon: '',
										classname: 'btn btn-info btn-xs btn-detail btn-dialog',
										url: 'users/duoge/index/user_id/{ids}',
										extend: 'data-area=\'["80%","80%"]\'',
									},
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
                    ]
                });
				
				// 清空金币
				$(document).on('click', '.btn-coinclear', function () {
					var ids = Table.api.selectedids(table4);
					Layer.confirm(__('确认清空金币吗', ids.length),
						{icon: 3, title: __('Warning'), offset: 0, shadeClose: true, btn: [__('OK'), __('Cancel')]},
						function (index) {
							Fast.api.ajax({
								url: "gameuser/coinclear",
								type: "post",
								data: {ids: ids},
							}, function () {
								table4.bootstrapTable('refresh', {});
							});
							Layer.close(index);
						}
					);
				});
				
                // 为表格4绑定事件
                Table.api.bindevent(table4);
            },
			five: function () {
                // 表格5
                var table5 = $("#table5");
				var game_id=Fast.api.query('game_id');
                table5.bootstrapTable({
                    url: 'games/loginlog/index/game_id/' + game_id,
                    toolbar: '#toolbar5',
                    sortName: 'id',
                    search: false,
                    columns: [
                        [
                            {field: 'id', title: __('Id'), operate: false},
							{field: 'user_id', title: '会员ID', formatter:Table.api.formatter.search},
							{field: 'user.username', title: '用户账号', operate: 'LIKE', formatter:Table.api.formatter.search},
							{field: 'game.name', title: '游戏名称', operate: 'LIKE', align: 'left', operate: false},
							{field: 'device_id', title: '设备号', operate: false},
							{field: 'ip', title: 'IP', formatter:Table.api.formatter.search},
							{field: 'create_time', title: '登陆时间', formatter: Table.api.formatter.datetime, operate: 'RANGE', addclass: 'datetimerange', sortable: true}
                        ]
                    ]
                });

                // 为表格5绑定事件
                Table.api.bindevent(table5);
            },
			six: function () {
                // 表格6
                var table6 = $("#table6");
				var game_id=Fast.api.query('game_id');
                table6.bootstrapTable({
                    url: 'games/live/index/game_id/' + game_id,
                    toolbar: '#toolbar6',
                    sortName: 'id',
                    search: false,
                    columns: [
                        [
                            {field: 'id', title: __('Id'), operate: false},
							{field: 'game.name', title: '游戏名称', align: 'left', operate: false},
							{field: 'num', title: '日活', sortable: true, operate: false,formatter: function (value) {
								return value*1;
							}},
							{field: 'date', title: '时间', formatter: Table.api.formatter.date, operate: 'RANGE', addclass: 'datetimerange', sortable: true}
                        ]
                    ]
                });

                // 为表格6绑定事件
                Table.api.bindevent(table6);
            },
			seven: function () {
                
				 // 基于准备好的dom，初始化echarts实例
				var myChart = Echarts.init(document.getElementById('echart'), 'walden');

				// 指定图表的配置项和数据
				var option = {
					title: {
						text: '',
						subtext: ''
					},
					color: [
						"#18d1b1",
						"#3fb1e3",
						"#626c91",
						"#a0a7e6",
						"#c4ebad",
						"#96dee8"
					],
					tooltip: {
						trigger: 'axis'
					},
					legend: {
						data: ['注册用户数']
					},
					toolbox: {
						show: false,
						feature: {
							magicType: {show: true, type: ['stack', 'tiled']},
							saveAsImage: {show: true}
						}
					},
					xAxis: {
						type: 'category',
						boundaryGap: false,
						data: Config.column
					},
					yAxis: {},
					grid: [{
						left: 'left',
						top: 'top',
						right: '10',
						bottom: 30
					}],
					series: [{
						name: '注册用户数',
						type: 'line',
						smooth: true,
						areaStyle: {
							normal: {}
						},
						lineStyle: {
							normal: {
								width: 1.5
							}
						},
						data: Config.userdata
					}]
				};

				// 使用刚指定的配置项和数据显示图表。
				myChart.setOption(option);
				
				
				var myChart1 = Echarts.init(document.getElementById('echart1'), 'walden');
				var option1 = {
					title: {
						text: '金额统计',
						subtext: ''
					},
					tooltip: {
						trigger: 'axis',
						//formatter: "{b}<br>{a0} : {c0} 元 <br>{a1} : {c1} 次 <br>{a2} : {c2} 个 <br>{a3} : {c3} 人"
					},
					legend: {
						data: ['预估收益API', '点击量', '金币', '日活']
					},
					toolbox: {
						show: true,
						feature: {
							dataView: {show: true, readOnly: false},
							magicType: {show: true, type: ['line', 'bar']},
							restore: {show: true},
							saveAsImage: {show: true}
						}
					},
					calculable: true,
					xAxis: [
						{
							type: 'category',
							data: Config.column1,
						}
					],
					yAxis: [
						{
							type: 'value'
						}
					],
					series: [
						{
							name: '预估收益API',
							type: 'line',
							data: Config.data1,
							markPoint: {
								data: [
									{type: 'max', name: '最大值'},
									{type: 'min', name: '最小值'}
								]
							},
							markLine: {
								data: [
									{type: 'average', name: '平均值'}
								]
							}
						},
						{
							name: '点击量',
							type: 'line',
							data: Config.data3,
							markPoint: {
								data: [
									{type: 'max', name: '最大值'},
									{type: 'min', name: '最小值'}
								]
							},
							markLine: {
								data: [
									{type: 'average', name: '平均值'}
								]
							}
						},
						{
							name: '金币',
							type: 'bar',
							smooth: true,
							symbol: 'none',
							data: Config.data2,
							markPoint: {
								data: [
									{type: 'max', name: '最大值'},
									{type: 'min', name: '最小值'}
								]
							},
							markLine: {
								data: [
									{type: 'average', name: '平均值'}
								]
							}
						},
						{
							name: '日活',
							type: 'bar',
							smooth: true,
							symbol: 'none',
							data: Config.data4,
							markPoint: {
								data: [
									{type: 'max', name: '最大值'},
									{type: 'min', name: '最小值'}
								]
							},
							markLine: {
								data: [
									{type: 'average', name: '平均值'}
								]
							}
						}
					]
				};
				myChart1.setOption(option1);
				
				
				var myChart3 = Echarts.init(document.getElementById('echart3'), 'macarons');
				var option3 = {
					title: {
						text: '账号分布',
						left: 'left'
					},
					tooltip: {
						trigger: 'item',
						formatter: function (row) {
							let {data} = row;
							let name = (data && data.name) || '';
							let value = (data && data.value) || 0;
							let coin = (data && data.coin) || 0;
							let rate = (data && data.rate) || 0;
							return name + ` : ( ${rate}% )<br/>账号数量 : ` + value + '个<br/>累计收益 : ' + coin + '个<br/>';
						}
					},
					legend: {
						orient: 'vertical',
						left: 'left',
						data: []
					},
					visualMap: {
						min: 0,
						max: 10000,
						left: 'left',
						top: 'bottom',
						text: ['高', '低'], // 文本，默认为数值文本
						calculable: true,
						inRange: {
							color: ['#f1f1f1', '#ff5200'] //取值范围的颜色
						},
						show: true //图注                   
					},
					toolbox: {
						show: true,
						orient: 'vertical',
						left: 'right',
						top: 'center',
						feature: {
							mark: {
								show: true
							},
							dataView: {
								show: true,
								readOnly: false
							},
							restore: {
								show: true
							},
							saveAsImage: {
								show: true
							}
						}
					},
					series: [{
						name: '账号分布',
						type: 'map',
						mapType: 'china',
						selectedMode: 'single',
						roam: false,
						zoom: 1.2,
						label: {
							normal: {
								show: true, //显示省份
								textStyle: {
									color: "#990000"
								}, //省份标签字体颜色
								formatter: '{b}'
							},
							emphasis: {
								show: true,
								textStyle: {
									color: "#323232"
								}
							}
						},
						data: Config.mapdata,
					}]
				};
				Config.mapdata.sort((a, b) => {
					return b.value - a.value;
				})
				option3.visualMap.max = Config.mapdata[0].value == 0 ? 5 : Config.mapdata[0].value;
				myChart3.setOption(option3);
				
				var myChart4 = Echarts.init(document.getElementById('echart4'), 'walden');
				var option4 = {
					title: {
						text: '账号分布',
						left:'center',
						bottom: '5%',
						textStyle:{
							fontSize: 14,
						}
					},
					tooltip: {
						trigger: 'item'
					},
					legend: {
						show:false,
					},
					grid: {
						left: '3%',
						right: '4%',
						bottom: '15%',
					},
					xAxis: {
						type: 'value',
						boundaryGap: [0, 0.01]
					},
					yAxis: {
						show:false,
						type: 'category',
						data: Config.mapdata1,
					},
					series: [{
						type: 'bar',
						label: {
							show: true,
							formatter: '{b}'
						},
						data: Config.mapdata2,
					}]
				};
				myChart4.setOption(option4);
				myChart4.resize();
				
				
				
            },
        },
        add: function () {
            Controller.api.bindevent();
        },
        edit: function () {
            Controller.api.bindevent();
        },
		coinedit: function () {
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