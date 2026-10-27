export async function api<T>(path:string, method='GET', body?:unknown):Promise<T> {
  const response=await fetch('/api'+path,{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});
  const data=await response.json();
  if(!response.ok) throw new Error(response.status===401?'AUTH_REQUIRED':typeof data.detail==='string'?data.detail:'The request could not be completed.');
  return data;
}
export function exportJSON(name:string,value:unknown){
  const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));
  const link=document.createElement('a');link.href=url;link.download=name;link.click();URL.revokeObjectURL(url);
}
