define(['jquery', 'bootstrap', 'backend', 'table', 'form'], function ($, undefined, Backend, Table, Form) {

    var Controller = {
        index: function () {
			var agent_id=Fast.api.query('agent_id');
			
            // 初始化表格参数配置
            Table.api.init({
                extend: {
                    index_url: 'agents/game/index/agent_id/' + agent_id,
                    add_url: 'agents/game/add/agent_id/' + agent_id,
                    edit_url: 'game/edit',
                    del_url: 'game/del',
                    multi_url: 'game/multi',
                    versionedit_url: 'game/versionedit',
                    coinadd_url: 'game/coinadd',
					distribution_url: 'game/distribution',
					privacy_url: 'game/privacy',
					other_url: 'game/other',
                    table: 'agents_game',
                }
            });
				
            var table = $("#table");
			
			//在普通搜索渲染后
            table.on('post-common-search.bs.table', function (event, table) {
                var form = $("form", table.$commonsearch);
				$("input[name='name']", form).addClass("selectpage").data("source", "ajax/gameList_source/agent_ids/" + agent_id);
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
                        {field: 'id', title: __('Id'), operate: false},
						{field: 'game_icon', title: '游戏Icon', events: Table.api.events.image, operate: false,
							formatter: function (value, row, index, custom) {
								if(row.game_ad_status == 1){
									var classname = typeof custom !== 'undefined' ? custom : 'img-sm img-center';
									//增加图片可以点击
									return '<a href="javascript:;"><img class="' + classname + '" src="' + Fast.api.cdnurl(value) + '" /></a>';
								}else{
									var classname = typeof custom !== 'undefined' ? custom : 'img-sm img-center';
									//增加图片可以点击
									return '<a href="javascript:;"><img class="' + classname + '" src="https://fa.war-game.cn/assets/img/ff.png" /></a>';
								}
							}
						},
						{field: 'name', title: '游戏名称', operate: 'LIKE', align: 'left'},
						{field: 'game_type', title: '类型', formatter: Table.api.formatter.label, searchList: {"0": '安卓APP', "1": '抖音小程序', "2": '微信小程序'}},
						{field: 'game_ad_status', title: '广告状态', formatter: Table.api.formatter.label, searchList: {"1": '正常', "2": '封应用', "3": '封主体'}, custom: {1: 'success', 2:'default', 3:'primary'}},
						{field: 'game_lottery_num', title: '金币异常概率', sortable: true, operate: false,formatter: function (value) {
                            return value*1 + '%';
                        }},
						{field: 'game_key', title: '游戏key', visible: false, operate: 'LIKE'},
				// 		{field: 'reg_num_total', title: '注册量', operate: false},
				// 		{field: 'live_month', title: '本月活跃', operate: false,formatter: function (value) {
    //                         return value*1;
    //                     }},
				// 		{field: 'live_day', title: '今日活跃', operate: false,formatter: function (value) {
    //                         return value*1;
    //                     }},
				// 		{field: 'coin_user_total', title: '累计用户金币收益', operate: false,formatter: function (value) {
    //                         return value*1;
    //                     }},
				// 		{field: 'coin_user_month', title: '本月用户金币收益', operate: false,formatter: function (value) {
    //                         return value*1;
    //                     }},
				// 		{field: 'coin_user_day', title: '今日用户金币收益', operate: false,formatter: function (value) {
    //                         return value*1;
    //                     }},
				// 		{field: 'coin_total', title: '可用金币', operate: false,formatter: function (value) {
    //                         return value*1;
    //                     }},
						{
                            field: 'buttons', title: '数据查看', table: table, operate: false,
                            events: Table.api.events.operate,
                            buttons: [
								{
									name: 'profitdata',
									title: '收益数据',
									text: '收益数据',
									icon: '',
									classname: 'btn btn-success btn-xs btn-detail btn-dialog',
									url: 'games/profitdata/index/game_id/{ids}',
									extend: 'data-area=\'["80%","80%"]\'',
								},
								{
									name: 'userdata',
									title: '用户数据',
									text: '用户数据',
									icon: '',
									classname: 'btn btn-info btn-xs btn-detail btn-dialog',
									url: 'games/userdata/index/game_id/{ids}',
									extend: 'data-area=\'["80%","80%"]\'',
								},
							],
                            formatter:function (value, row, index) {
								var that = $.extend({}, this);
								var table = $(that.table).clone(true);
								$(table).data("operate-edit", null);
								$(table).data("operate-del", null);
								that.table = table;
								return Table.api.formatter.operate.call(that, value, row, index);
                            },
                        },
						{field: 'game_url', title: '游戏链接地址', visible: false, operate: false},
						{field: 'countdown', title: '倒计时', visible: false, operate: false},
						{field: 'raffle_num', title: '抽奖次数', visible: false, operate: false,formatter: function (value) {
                            return value*1;
                        }},
						{field: 'raffle_coin', title: '抽奖失败补偿金币', visible: false, operate: false},
						{field: 'ordinary_num', title: '普通广告位', visible: false, operate: false,formatter: function (value) {
                            return value*1 + '%';
                        }},
						{field: 'client_num', title: 'client竞价广告', visible: false, operate: false,formatter: function (value) {
                            return value*1 + '%';
                        }},
						{field: 'server_num', title: 'server竞价广告', visible: false, operate: false,formatter: function (value) {
                            return value*1 + '%';
                        }},
						{field: 'multiorder_num', title: '多阶底价', visible: false, operate: false,formatter: function (value) {
                            return value*1 + '%';
                        }},
						{field: 'player_num', title: 'P层数据', visible: false, operate: false,formatter: function (value) {
                            return value*1 + '%';
                        }},
						{field: 'ad_incentive_video_status', title: '激励视频广告状态', visible: false, operate: false, formatter: Table.api.formatter.toggle},
						{field: 'ad_open_screen_video_status', title: '开屏广告状态', visible: false, operate: false, formatter: Table.api.formatter.toggle},
						{field: 'ad_full_screen_video_status', title: '全屏广告状态', visible: false, operate: false, formatter: Table.api.formatter.toggle},
						{field: 'ad_banner_status', title: 'Banner广告状态', visible: false, operate: false, formatter: Table.api.formatter.toggle},
						{field: 'ad_plaque_status', title: '插屏广告状态', visible: false, operate: false, formatter: Table.api.formatter.toggle},
						{field: 'commission_status', title: '独立分拥状态', visible: false, operate: false, searchList: {"1": '启用', "0": '禁用'}, formatter: Table.api.formatter.toggle},
						{field: 'commission_source', title: '分拥来源', visible: false, operate: false, formatter: Table.api.formatter.label, custom: {0: 'info', 1:'success'}, searchList: {"0": '代理', "1": '下级'}},
						{field: 'commission_rate', title: '分佣比例', visible: false, operate: false,formatter: function (value) {
                            return value*1 + '%';
                        }},
						{field: 'is_landscape', title: '横竖屏', visible: false, searchList: {"1": '横屏', "0": '竖屏'}, formatter: Table.api.formatter.label},
						{field: 'ad_status', title: '广告状态', visible: false, searchList: {"1": '启用', "0": '禁用'}, formatter: Table.api.formatter.toggle},
						{field: 'status', title: '上架状态', operate: false, searchList: {"1": '上架', "0": '下架'}, formatter: Table.api.formatter.toggle},
                        {field: 'create_time', title: __('Createtime'), formatter: Table.api.formatter.datetime, operate: 'RANGE', addclass: 'datetimerange', sortable: true},
						{
                            field: 'operate', title: __('Operate'), table: table,
                            events: Table.api.events.operate,
                            buttons: [
								{
									name: 'qdedit',
									title: '签到配置',
									text: '签到配置',
									icon: '',
									classname: 'btn btn-info btn-xs btn-detail btn-dialog',
									url: 'game/qdedit',
								},
        //                         {
								// 	name: 'coinadd',
								// 	title: '赠送金币',
								// 	text: '赠送金币',
								// 	icon: '',
								// 	classname: 'btn btn-warning btn-xs btn-detail btn-dialog',
								// 	url: 'game/coinadd',
								// },
								{
									name: 'versionedit',
									title: '版本配置',
									text: '',
									icon: 'fa fa-cog',
									classname: 'btn btn-info btn-xs btn-detail btn-dialog',
									url: 'game/versionedit'
								},
								// {
								// 	name: 'distribution',
								// 	title: '分销配置',
								// 	text: '',
								// 	icon: 'fa fa-users',
								// 	classname: 'btn btn-primary btn-xs btn-detail btn-dialog',
								// 	url: 'game/distribution'
								// },
								{
									name: 'privacy',
									title: '隐私政策',
									text: '隐私政策',
									icon: '',
									classname: 'btn btn-info btn-xs btn-detail btn-dialog',
									url: 'game/privacy',
								},
								// {
								// 	name: 'pricesetedit',
								// 	title: '红包配置',
								// 	text: '',
								// 	icon: 'fa fa-soccer-ball-o',
								// 	classname: 'btn btn-primary btn-xs btn-detail btn-dialog',
								// 	url: 'game/pricesetedit'
								// },
								{
									name: 'other',
									title: '其它',
									text: '其它',
									icon: '',
									classname: 'btn btn-info btn-xs btn-detail btn-dialog',
									url: 'game/other',
								},
							],
                            formatter: Table.api.formatter.operate
                        }
                    ]
                ],
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
        coinadd: function () {
            Controller.api.bindevent();
        },
		versionedit: function () {
            Controller.api.bindevent();
        },
		distribution: function () {
            Controller.api.bindevent();
        },
		privacy: function () {
            Controller.api.bindevent();
        },
		other: function () {
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


