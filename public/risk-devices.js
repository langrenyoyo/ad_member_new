async function renderRiskDevices(){
 if(state.view!=='risk-devices')return;
 $('#content').innerHTML='<div id="memberPolicyHost"></div><div id="aliyunRiskHost"></div>';
 mountMemberPolicy(document.querySelector('#memberPolicyHost'));
 await mountAliyunRisk(document.querySelector('#aliyunRiskHost'));
}
