
(()=>{if(matchMedia('(prefers-reduced-motion: reduce)').matches)return;
const seen=new WeakSet();const observer=new IntersectionObserver(items=>{for(const item of items)if(item.isIntersecting){item.target.classList.add('is-route-visible');observer.unobserve(item.target)}},{threshold:.2});
let pending=false;function scan(){pending=false;document.querySelectorAll('.journey-scroll').forEach(el=>{if(!seen.has(el)){seen.add(el);observer.observe(el)}})}
const app=document.getElementById('app');if(app)new MutationObserver(()=>{if(!pending){pending=true;requestAnimationFrame(scan)}}).observe(app,{subtree:true,childList:true});scan();
})();
