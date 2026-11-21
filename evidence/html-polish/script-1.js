
(()=>{if(matchMedia('(prefers-reduced-motion: reduce)').matches)return;
const seen=new WeakSet();
const enter=new IntersectionObserver(entries=>{for(const e of entries)if(e.isIntersecting){e.target.classList.add('tm-enter');enter.unobserve(e.target)}},{threshold:.08});
let scheduled=false;
function scan(){scheduled=false;document.querySelectorAll('.welcome,.gallery article,.destination-heading,.destination-card,.page-heading,.settings form section,.stop,.subheading').forEach(el=>{if(!seen.has(el)){seen.add(el);enter.observe(el)}})}
const root=document.getElementById('app');if(!root)return;
new MutationObserver(()=>{if(!scheduled){scheduled=true;requestAnimationFrame(scan)}}).observe(root,{childList:true,subtree:true});scan();
})();
