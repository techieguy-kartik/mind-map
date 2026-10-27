import {useState} from 'react';
import {Expand, Minus, Plus, RotateCcw, ArrowUpRight} from 'lucide-react';
import type {Entity,Edge} from './types';

export function Graph({entities,edges,onEntity,onEdge,compact=false}:{entities:Entity[];edges:Edge[];onEntity:(id:string)=>void;onEdge:(edge:Edge)=>void;compact?:boolean}){
  const [selected,setSelected]=useState<string|null>(null);
  const [scale,setScale]=useState(1);
  const [offset,setOffset]=useState({x:0,y:0});
  const [drag,setDrag]=useState<{x:number;y:number;ox:number;oy:number}|null>(null);
  const connected=new Set(edges.flatMap(e=>[e.source,e.target]));
  const nodes=entities.filter(e=>connected.has(e.id));
  const positions=new Map(nodes.map((n,i)=>{
    const angle=(i/Math.max(nodes.length,1))*Math.PI*2-Math.PI/2;
    return [n.id,{x:400+Math.cos(angle)*270,y:245+Math.sin(angle)*165}];
  }));
  const active=new Set(selected?[selected,...edges.filter(e=>e.source===selected||e.target===selected).flatMap(e=>[e.source,e.target])]:nodes.map(n=>n.id));
  return <div className={'graph-canvas '+(compact?'compact':'')}>
    <div className="graph-caption"><span className="live-dot"/> {nodes.length} entities · {edges.length} evidenced connections</div>
    {nodes.length===0?<div className="graph-empty"><Expand size={32}/><h3>No accepted relationships yet</h3><p>Headlines alone do not establish a business relationship.<br/>The demonstration dataset shows the graph interaction.</p></div>:
    <svg viewBox="0 0 800 500" aria-label="Interactive company intelligence graph" role="group"
      onPointerDown={e=>{if(e.target===e.currentTarget){e.currentTarget.setPointerCapture(e.pointerId);setDrag({x:e.clientX,y:e.clientY,ox:offset.x,oy:offset.y});}}}
      onPointerMove={e=>{if(drag)setOffset({x:drag.ox+(e.clientX-drag.x),y:drag.oy+(e.clientY-drag.y)});}}
      onPointerUp={()=>setDrag(null)} onPointerCancel={()=>setDrag(null)}>
      <g transform={`translate(${offset.x} ${offset.y}) translate(400 250) scale(${scale}) translate(-400 -250)`}>
        {edges.map((edge,i)=>{const a=positions.get(edge.source),b=positions.get(edge.target);if(!a||!b)return null;const highlighted=!selected||edge.source===selected||edge.target===selected;const control={x:400,y:210+(i%3)*35};const curve=`M${a.x},${a.y} Q${control.x},${control.y} ${b.x},${b.y}`;const mid={x:.25*a.x+.5*control.x+.25*b.x,y:.25*a.y+.5*control.y+.25*b.y};
          return <g key={edge.id} opacity={highlighted?1:.16}>
            <path d={curve} fill="none" stroke={selected?'#528c78':'#b9c9bf'} strokeWidth={selected?'2':'1.3'} strokeDasharray={edge.demo?'5 4':undefined} pointerEvents="none"/>
            <circle cx={mid.x} cy={mid.y} r="6" fill="#f8f9f4" stroke="#829982" strokeWidth="1.5" className="graph-edge-hit" tabIndex={0} role="button" aria-label={`Inspect ${edge.relation} between ${entities.find(n=>n.id===edge.source)?.name} and ${entities.find(n=>n.id===edge.target)?.name}`} onClick={()=>onEdge(edge)} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();onEdge(edge);}}}/>
          </g>;})}
        {nodes.map(n=>{const p=positions.get(n.id)!;const chosen=selected===n.id;return <g key={n.id} transform={`translate(${p.x} ${p.y})`} tabIndex={0} role="button" aria-label={`Select ${n.name}`} onClick={()=>setSelected(chosen?null:n.id)} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();setSelected(chosen?null:n.id);}}} className="graph-node" opacity={active.has(n.id)?1:.25}>
          {chosen&&<circle r="35" fill="none" stroke="#6c9c82" strokeWidth="2"/>}
          <circle r={n.type==='technology'?21:26} fill={n.type==='technology'?'#f1ece2':'white'} stroke={n.color} strokeWidth="1.5"/>
          <text textAnchor="middle" y="5" fill={n.color} fontSize="14" fontWeight="700">{n.initials}</text>
          <rect x="-83" y="34" width="166" height="22" rx="8" fill="#f7f8f2" fillOpacity=".94"/>
          <text textAnchor="middle" y="49" fill="#3b4b43" fontSize="12" fontWeight="500">{n.name.length>24?n.name.slice(0,22)+'…':n.name}</text>
        </g>;})}
      </g>
    </svg>}
    <div className="graph-footer"><div className="legend"><span><i className="company-dot"/>Company</span><span><i className="tech-dot"/>Technology</span><span className="dashed-legend">– – Illustrative edge</span></div><div className="graph-controls"><button aria-label="Zoom out" onClick={()=>setScale(Math.max(.6,scale-.15))}><Minus size={15}/></button><button aria-label="Reset graph" onClick={()=>{setScale(1);setOffset({x:0,y:0});setSelected(null);}}><RotateCcw size={14}/></button><button aria-label="Zoom in" onClick={()=>setScale(Math.min(2,scale+.15))}><Plus size={15}/></button></div></div>
    {selected&&<button className="graph-selected" onClick={()=>onEntity(selected)}>Open {entities.find(n=>n.id===selected)?.name}<ArrowUpRight size={15}/></button>}
  </div>;
}
