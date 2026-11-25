'use strict';
const live=document.querySelector('[data-live]');
if(live){
 let busy=false;
 async function refresh(){
  if(document.hidden||busy)return;busy=true;
  const status=document.getElementById('sync-status');
  try{
   const url=new URL(location.href);url.searchParams.set('format','json');
   const response=await fetch(url,{credentials:'same-origin',signal:AbortSignal.timeout(8000)});
   if(!response.ok||!response.headers.get('content-type')?.includes('application/json'))throw Error('sync');
   const data=await response.json(),fragment=document.createDocumentFragment();
   for(const b of data.bookings){
    const a=document.createElement('a');a.className='booking-row';a.href='/owner/booking/'+b.id+'/';
    const person=document.createElement('div'),name=document.createElement('strong'),phone=document.createElement('small');
    name.textContent=b.name;phone.textContent=b.phone;phone.dir='ltr';person.append(name,phone);
    const info=document.createElement('div'),time=document.createElement('small');info.append(document.createTextNode(b.service));time.textContent=b.time;info.append(time);
    const state=document.createElement('span');state.className='badge';state.textContent=b.status;
    const arrow=document.createElement('span');arrow.textContent='←';a.append(person,info,state,arrow);fragment.append(a);
   }
   if(!data.bookings.length){const p=document.createElement('p');p.className='empty';p.textContent='مفيش حجوزات في الفترة دي.';fragment.append(p);}
   live.replaceChildren(fragment);status.textContent='آخر تحديث دلوقتي · تحديث تلقائي كل ١٠ ثواني';
  }catch(e){status.textContent='التحديث التلقائي وقف مؤقتًا. هنحاول تاني، أو حدث الصفحة.';}
  finally{busy=false;}
 }
 setInterval(refresh,10000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
}
for(const form of document.querySelectorAll('form[method="post"]')){
 form.addEventListener('submit',()=>{const button=form.querySelector('button[type="submit"],button:not([type])');if(button){button.disabled=true;button.dataset.label=button.textContent;button.textContent='جاري الحفظ…';}});
}
window.addEventListener('pageshow',()=>{for(const b of document.querySelectorAll('button[data-label]')){b.disabled=false;b.textContent=b.dataset.label;}});
