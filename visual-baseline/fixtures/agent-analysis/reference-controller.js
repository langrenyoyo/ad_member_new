define(['jquery', 'bootstrap', 'backend', 'addtabs', 'table', 'echarts', 'echarts-theme', 'template', 'form'], function ($, undefined, Backend, Datatable, Table, Echarts, undefined, Template, Form) {
    var Controller = {
        index: function () {
			var agent_id=Fast.api.query('agent_id');
			
            // 初始化表格参数配置
            Table.api.init({
                extend: {
                    index_url: 'agents/assay/index/agent_id/' + agent_id,
					edit_url: 'gameuser/edit',
					usercoinedit_url: 'gameuser/coinedit',
                    del_url: 'gameuser/del',
                    multi_url: 'gameuser/multi',
                    coinedit_url: 'assay/coinedit',
                    successpercentedit_url: 'assay/successpercentedit',
                    appnumedit_url: 'assay/appnumedit',
                    table: 'agents_assay',
                }
            });
				
            var table = $("#table");
			
            // 初始化表格
            table.bootstrapTable({
                url: $.fn.bootstrapTable.defaults.extend.index_url,
                pk: 'id',
                sortName: 'user.id',
                columns: [
                    [
						{field: 'id', title: __('Id'), operate: false},
						{field: 'user.username', title: '账号', operate: false},
						{field: 'game.name', title: '游戏名称', operate: false, align: 'left'},
						{field: 'agent.name', title: '代理商名称', operate: false, align: 'left'},
						{field: 'user.coin_user', title: '累计金币收益', sortable: true, operate: false,formatter: function (value) {
                            return value*1;
                        }},
						{field: 'user.coin_user_month', title: '本月金币收益', operate: false,formatter: function (value) {
                            return value*1;
                        }},
						{field: 'user.coin_user_day', title: '今日金币收益', operate: false,formatter: function (value) {
                            return value*1;
                        }},
						{field: 'user.coin', title: '可用金币', sortable: true, operate: false,formatter: function (value) {
                            return value*1;
                        }},
						{field: 'user.freeze_coin', title: '冻结金币', sortable: true, operate: false,formatter: function (value) {
                            return value*1;
                        }},
						{field: 'user.game_addiction_enable', title: '达标', formatter: Table.api.formatter.label, custom: {0: 'info', 1:'success'}, searchList: {"0": '否', "1": '是'}, operate: false},
						{field: 'is_white', title: '白名单', searchList: {"1": '是', "0": '否'}, operate: false, formatter: Table.api.formatter.toggle},
						{field: 'status', title: '状态', searchList: {"1": '启用', "0": '禁用'}, operate: false, formatter: Table.api.formatter.toggle},
						{field: 'user.create_time', title: __('Createtime'), formatter: Table.api.formatter.datetime, operate: 'RANGE', operate: false, addclass: 'datetimerange', sortable: true},
						{
                            field: 'operate', title: __('Operate'), table: table,
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
									name: 'usercoinedit',
									title: '修改金币',
									text: '修改金币',
									icon: '',
									classname: 'btn btn-warning btn-xs btn-detail btn-dialog',
									url: 'gameuser/coinedit',
								},
							],
                            formatter: Table.api.formatter.operate
                        },
						
						{field: 'coin_user_total', title: '累计用户金币收益', visible: false, sortable: true, operate: 'BETWEEN',formatter: function (value) {
                            return value*1;
                        }},
						{field: 'coin_every', title: '每次抽奖金币收益', visible: false, sortable: true, operate: 'BETWEEN',formatter: function (value) {
                            return value*1;
                        }},
						{field: 'lottery_num', title: '抽奖次数', visible: false, sortable: true, operate: false,formatter: function (value) {
                            return value*1;
                        }},
						{field: 'lottery_num_success', title: '成功次数', visible: false, sortable: true, operate: false,formatter: function (value) {
                            return value*1;
                        }},
						{field: 'success_percent', title: '成功率', visible: false, sortable: true, operate: 'BETWEEN',formatter: function (value) {
                            return value*1 + '%';
                        }},
						{field: 'lottery_num_fail', title: '失败次数', visible: false, sortable: true, operate: false,formatter: function (value) {
                            return value*1;
                        }},
						{field: 'fail_percent', title: '失败率', visible: false, sortable: true, operate: false,formatter: function (value) {
                            return value*1 + '%';
                        }},
						{field: 'app_num', title: 'APP数量', visible: false, sortable: true, operate: 'BETWEEN',formatter: function (value) {
                            return value*1;
                        }},
						{field: 'create_time', title: '抽奖时间', visible: false, formatter: Table.api.formatter.datetime, operate: 'RANGE', addclass: 'datetimerange', sortable: true},
                    ]
                ],
                pagination: true,
                search: false,
                commonSearch: true,
				searchFormVisible: true,
                showSearch: false,
				showToggle: false,
				showColumns: false,
				showExport: false,
            });
			
            // 为表格绑定事件
            Table.api.bindevent(table);
			
			table.on('load-success.bs.table', function (e, json) {
				var myChart1 = Echarts.init(document.getElementById('echart1'), 'walden');
				var option1 = {
					title: {
						show:false,
					},
					tooltip: {
						trigger: 'item'
					},
					legend: {
						show:false,
					},
					series: [
						{
							type: 'pie',
							radius: '70%',
							label: {
								normal: {
									show: true,
									//formatter: '{b}: {c}({d}%)'
									formatter: '{b}({d}%)'
								},
							},
							data: json.echart_data.echart_coin_data,
							emphasis: {
								itemStyle: {
									shadowBlur: 10,
									shadowOffsetX: 0,
									shadowColor: 'rgba(0, 0, 0, 0.5)'
								}
							}
						}
					]
				};
				myChart1.setOption(option1);
				myChart1.resize();
				
				var myChart2 = Echarts.init(document.getElementById('echart2'), 'walden');
				var option2 = {
					title: {
						show:false,
					},
					tooltip: {
						trigger: 'item'
					},
					legend: {
						show:false,
					},
					series: [
						{
							type: 'pie',
							radius: '70%',
							label: {
								normal: {
									show: true,
									//formatter: '{b}: {c}({d}%)'
									formatter: '{b}({d}%)'
								},
							},
							data: json.echart_data.echart_success_percent_data,
							emphasis: {
								itemStyle: {
									shadowBlur: 10,
									shadowOffsetX: 0,
									shadowColor: 'rgba(0, 0, 0, 0.5)'
								}
							}
						}
					]
				};
				myChart2.setOption(option2);
				myChart2.resize();
				
				var myChart3 = Echarts.init(document.getElementById('echart3'), 'walden');
				var option3 = {
					title: {
						show:false,
					},
					tooltip: {
						trigger: 'item'
					},
					legend: {
						show:false,
					},
					series: [
						{
							type: 'pie',
							radius: '70%',
							label: {
								normal: {
									show: true,
									//formatter: '{b}: {c}({d}%)'
									formatter: '{b}({d}%)'
								},
							},
							data: json.echart_data.echart_ip_data,
							emphasis: {
								itemStyle: {
									shadowBlur: 10,
									shadowOffsetX: 0,
									shadowColor: 'rgba(0, 0, 0, 0.5)'
								}
							}
						}
					]
				};
				myChart3.setOption(option3);
				myChart3.resize();
				
				var myChart4 = Echarts.init(document.getElementById('echart4'), 'walden');
				var option4 = {
					title: {
						show:false,
					},
					tooltip: {
						trigger: 'item'
					},
					legend: {
						show:false,
					},
					series: [
						{
							type: 'pie',
							radius: '70%',
							label: {
								normal: {
									show: true,
									//formatter: '{b}: {c}({d}%)'
									formatter: '{b}({d}%)'
								},
							},
							data: json.echart_data.echart_app_num_data,
							emphasis: {
								itemStyle: {
									shadowBlur: 10,
									shadowOffsetX: 0,
									shadowColor: 'rgba(0, 0, 0, 0.5)'
								}
							}
						}
					]
				};
				myChart4.setOption(option4);
				myChart4.resize();
				
				var myChart6 = Echarts.init(document.getElementById('echart6'), 'walden');
				var option6 = {
					title: {
						text: 'APP来源',
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
						data: json.echart_data.echart_game_data.name,
					},
					series: [{
						type: 'bar',
						label: {
							show: true,
							formatter: '{b}'
						},
						data: json.echart_data.echart_game_data.value,
					}]
				};
				myChart6.setOption(option6);
				myChart6.resize();
				
				var myChart7 = Echarts.init(document.getElementById('echart7'), 'walden');
				var option7 = {
					title: {
						text: '总金币平均金币散点图',
						left:'center',
						bottom: '5%',
						textStyle:{
							fontSize: 14,
						}
					},
					
					grid: {
						right: '4%',
						bottom: '15%',
					},
					xAxis: {
						scale: true
					},
					yAxis: {
						scale: true
					},
					series: [{
						type: 'scatter',
						data: json.echart_data.echart_scatter_data,
					}]
				};
				myChart7.setOption(option7);
				myChart7.resize();
				
            });
			
			
        },
        add: function () {
            Controller.api.bindevent();
        },
        edit: function () {
            Controller.api.bindevent();
        },
		usercoinedit: function () {
            Controller.api.bindevent();
        },
		coinedit: function () {
			Form.api.bindevent($("form[role=form]"), function(data, ret){
				parent.$('button[type=submit]').trigger("click");
			})
        },
		successpercentedit: function () {
			Form.api.bindevent($("form[role=form]"), function(data, ret){
				parent.$('button[type=submit]').trigger("click");
			})
        },
		appnumedit: function () {
			Form.api.bindevent($("form[role=form]"), function(data, ret){
				parent.$('button[type=submit]').trigger("click");
			})
        },
        api: {
            bindevent: function () {
                Form.api.bindevent($("form[role=form]"));
            }
        }
    };
    return Controller;
});


