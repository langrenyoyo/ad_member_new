let reviewDatesReady;
const reviewDateBindings=new Map();
async function loadReviewDates(){
 if(!reviewDatesReady)reviewDatesReady=(async()=>{
  await loadReviewJQuery();
  if(!window.moment)await loadReviewScript('/vendor/moment.min.js');
  if(!window.jQuery.fn.daterangepicker)await loadReviewScript('/vendor/daterangepicker.js');
  if(!document.querySelector('link[data-review-dates]')){
   const link=document.createElement('link');link.rel='stylesheet';link.href='/vendor/daterangepicker.css';link.dataset.reviewDates='true';document.head.append(link);
  }
 })().catch(error=>{reviewDatesReady=undefined;throw error;});
 return reviewDatesReady;
}
function attachReviewDates(form,selector='input[name$="_range"]',localeOverrides={}){
 form.querySelectorAll(selector).forEach(input=>{
  input.autocomplete='off';
  input.addEventListener('focus',async()=>{
   try{
    await loadReviewDates();
    if(!input.isConnected||document.activeElement!==input)return;
    if(!reviewDateBindings.has(input)){
     const m=window.moment,today=m().utcOffset(480),format='YYYY-MM-DD HH:mm:ss';
     const ranges={
      '今天':[today.clone().startOf('day'),today.clone().endOf('day')],
      '昨天':[today.clone().subtract(1,'day').startOf('day'),today.clone().subtract(1,'day').endOf('day')],
      '最近7天':[today.clone().subtract(6,'days').startOf('day'),today.clone().endOf('day')],
      '最近30天':[today.clone().subtract(29,'days').startOf('day'),today.clone().endOf('day')],
      '本月':[today.clone().startOf('month'),today.clone().endOf('month')],
      '上月':[today.clone().subtract(1,'month').startOf('month'),today.clone().subtract(1,'month').endOf('month')]
     };
     const values=input.value.split(' - ').map(value=>m(value,format,true));
     const valid=values.length===2&&values.every(value=>value.isValid())&&!values[0].isAfter(values[1]);
     const element=window.jQuery(input);
     element.daterangepicker({parentEl:input.closest('dialog')||document.body,timePicker:false,autoUpdateInput:false,timePickerSeconds:true,timePicker24Hour:true,autoApply:true,
      startDate:valid?values[0]:today.clone().startOf('day'),endDate:valid?values[1]:today.clone().endOf('day'),ranges,
      locale:{format,separator:' - ',customRangeLabel:'自定义',applyLabel:'确定',cancelLabel:'清空',daysOfWeek:['日','一','二','三','四','五','六'],monthNames:['一月','二月','三月','四月','五月','六月','七月','八月','九月','十月','十一月','十二月'],firstDay:1,...localeOverrides}
     });
     element.on('apply.daterangepicker',(event,picker)=>{input.value=picker.startDate.format(format)+' - '+picker.endDate.format(format);input.dispatchEvent(new Event('change',{bubbles:true}));input.blur();});
     element.on('cancel.daterangepicker',()=>{input.value='';input.dispatchEvent(new Event('change',{bubbles:true}));input.blur();});
     reviewDateBindings.set(input,element.data('daterangepicker'));
    }
    reviewDateBindings.get(input).show();
   }catch(error){const box=form.closest('dialog')?.querySelector('[role=alert]')||document.querySelector('#reviewError');if(input.isConnected&&box)box.textContent=error.message;}
  });
 });
}
const reviewDateObserver=new MutationObserver(()=>{
 for(const [input,picker] of reviewDateBindings)if(!input.isConnected){picker.hide();picker.remove();reviewDateBindings.delete(input);}
});
reviewDateObserver.observe(document.body,{childList:true,subtree:true});
