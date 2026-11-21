import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const base=path.dirname(fileURLToPath(import.meta.url));
const spec=JSON.parse(await fs.readFile(path.join(base,'api-v1.json'),'utf8'));
const errors=[]; let checks=0;
function validate(value,schema,p='$'){
 if(schema.$ref){let t=spec;for(const k of schema.$ref.slice(2).split('/'))t=t[k];if(!t)return [p+': unresolved reference'];return validate(value,t,p)}
 if(schema.anyOf||schema.oneOf){const choices=schema.anyOf||schema.oneOf;const ok=choices.filter(s=>validate(value,s,p).length===0).length;return (schema.oneOf?ok===1:ok>=1)?[]:[p+': union mismatch']}
 const e=[];const t=schema.type;
 if(t==='null')return value===null?[]:[p+': expected null'];
 if(t==='object'){
  if(value===null||typeof value!=='object'||Array.isArray(value))return[p+': expected object'];
  for(const k of schema.required||[])if(!(k in value))e.push(p+'.'+k+': required');
  for(const [k,v]of Object.entries(value)){if(schema.properties?.[k])e.push(...validate(v,schema.properties[k],p+'.'+k));else if(schema.additionalProperties===false)e.push(p+'.'+k+': unknown')}
 }else if(t==='array'){
  if(!Array.isArray(value))return[p+': expected array'];
  if(schema.minItems!==undefined&&value.length<schema.minItems)e.push(p+': minItems');
  if(schema.maxItems!==undefined&&value.length>schema.maxItems)e.push(p+': maxItems');
  if(schema.uniqueItems&&new Set(value.map(v=>JSON.stringify(v))).size!==value.length)e.push(p+': uniqueItems');
  value.forEach((v,i)=>e.push(...validate(v,schema.items,p+'['+i+']')));
 }else{
  if(t==='integer'&&!Number.isInteger(value))e.push(p+': expected integer');
  else if(t&&t!=='integer'&&typeof value!==t)e.push(p+': expected '+t);
  if(typeof value==='number'){if(schema.minimum!==undefined&&value<schema.minimum)e.push(p+': minimum');if(schema.maximum!==undefined&&value>schema.maximum)e.push(p+': maximum')}
  if(typeof value==='string'){
   if(schema.minLength!==undefined&&value.length<schema.minLength)e.push(p+': minLength');
   if(schema.maxLength!==undefined&&value.length>schema.maxLength)e.push(p+': maxLength');
   if(schema.pattern&&!new RegExp(schema.pattern).test(value))e.push(p+': pattern');
   if(schema.format==='date'&&!/^\d{4}-\d{2}-\d{2}$/.test(value))e.push(p+': date');
   if(schema.format==='date-time'&&Number.isNaN(Date.parse(value)))e.push(p+': date-time');
   if(schema.format==='uri'){try{new URL(value)}catch{e.push(p+': uri')}}
  }
 }
 if(schema.enum&&!schema.enum.includes(value))e.push(p+': enum');
 return e;
}
function check(v,s,label){checks++;errors.push(...validate(v,s,label))}
const index=JSON.parse(await fs.readFile(path.join(base,'mock/index.json'),'utf8'));
const covered=new Set();
for(const entry of index.cases){
 const c=JSON.parse(await fs.readFile(path.join(base,'mock',entry.file),'utf8'));
 const op=spec.paths[c.path]?.[c.method.toLowerCase()];
 if(!op||op.operationId!==c.operationId){errors.push(c.name+': missing operation');continue}
 covered.add(c.operationId);
 const req=op.requestBody?.content['application/json'].schema;
 if(req){const result=validate(c.request,req,c.name+'.request');checks++;if(c.name==='invalid-input'){if(!result.length)errors.push(c.name+': invalid request unexpectedly valid')}else errors.push(...result)}
 const response=op.responses[String(c.expectedStatus)]?.content?.['application/json']?.schema;
 if(!response)errors.push(c.name+': undocumented status');else check(c.response,response,c.name+'.response');
}
for(const item of Object.values(spec.paths))for(const op of Object.values(item))if(!covered.has(op.operationId))errors.push(op.operationId+': no mock');
const seed=JSON.parse(await fs.readFile(path.join(base,'attractions.seed.json'),'utf8'));
const matrix=JSON.parse(await fs.readFile(path.join(base,'travel_times.json'),'utf8'));
const state=JSON.parse(await fs.readFile(path.join(base,'demo_state.seed.json'),'utf8'));
for(const a of seed.items)check(a,spec.components.schemas.Attraction,a.id);
check(state,spec.components.schemas.State,'seed-state');
const ids=['start',...seed.items.map(a=>a.id)];
if(new Set(ids).size!==ids.length)errors.push('duplicate attraction ID');
for(const a of ids)for(const b of ids){checks++;const v=matrix.minutes[a]?.[b];if(!Number.isInteger(v)||v<0||matrix.minutes[b]?.[a]!==v||(a===b&&v!==0))errors.push('matrix '+a+' '+b)}
function refs(s){if(!s||typeof s!=='object')return;if(s.$ref){let v=spec;for(const k of s.$ref.slice(2).split('/'))v=v?.[k];if(!v)errors.push('unresolved '+s.$ref)}for(const v of Object.values(s))if(typeof v==='object')refs(v)}
refs(spec);
const scenarios=JSON.parse(await fs.readFile(path.join(base,'scenarios.json'),'utf8'));
for(const c of scenarios.cases)check(c.request,spec.components.schemas.ReplanRequest,'scenario.'+c.id);
const report={passed:errors.length===0,contractVersion:spec.info.version,operations:covered.size,mockCases:index.cases.length,attractions:seed.items.length,checks,errors,scope:'结构、样例、引用和矩阵一致性检查；不是已实现服务或业务算法验收。'};
await fs.mkdir(path.resolve(base,'../evidence/contracts'),{recursive:true});
await fs.writeFile(path.resolve(base,'../evidence/contracts/validation.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
if(errors.length)process.exitCode=1;
