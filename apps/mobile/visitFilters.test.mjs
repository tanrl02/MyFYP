import test from "node:test";
import assert from "node:assert/strict";
import {filterVisits} from "./patientVisitFilter.ts";

const now=Date.parse("2032-10-23T01:00:00Z");
const token=visit=>`${visit.doctor_id==="doctor-lim"?"L":"A"}${String(visit.queue_number).padStart(3,"0")}`;
function fixture(){return [
  {id:"future",doctor_id:"doctor-lim",doctor_name:"Dr. Lim (demo)",queue_number:1,status:"waiting",starts_at:"2032-10-24T09:00:00+08:00",rescheduled_to_id:null},
  {id:"called",doctor_id:"doctor-anita",doctor_name:"Dr. Anita (demo)",queue_number:2,status:"called",starts_at:"2032-10-23T09:00:00+08:00",rescheduled_to_id:null},
  {id:"past",doctor_id:"doctor-lim",doctor_name:"Dr. Lim (demo)",queue_number:3,status:"waiting",starts_at:"2032-10-23T08:59:59+08:00",rescheduled_to_id:null},
  ...["completed","cancelled","missed"].map((status,i)=>({id:status,doctor_id:"doctor-lim",doctor_name:"Dr. Lim (demo)",queue_number:i+4,status,starts_at:"2032-10-24T09:00:00+08:00",rescheduled_to_id:null})),
  {id:"moved",doctor_id:"doctor-anita",doctor_name:"Dr. Anita (demo)",queue_number:7,status:"cancelled",starts_at:"2032-10-24T09:00:00+08:00",rescheduled_to_id:"replacement"}
];}
test("search matches the displayed doctor or queue token without case or surrounding-space sensitivity",()=>{
  const visits=fixture();
  assert.deepEqual(filterVisits(visits,"  aNiTa ","all",token,now).map(v=>v.id),["called","moved"]);
  assert.deepEqual(filterVisits(visits," l001 ","all",token,now).map(v=>v.id),["future"]);
  assert.equal(filterVisits(visits,"","all",token,now).length,7);
  assert.equal(filterVisits(visits,"nonexistent","all",token,now).length,0);
});
test("upcoming uses active status and normalised scheduled time with an inclusive boundary",()=>{
  assert.deepEqual(filterVisits(fixture(),"","upcoming",token,now).map(v=>v.id),["future","called"]);
  assert.deepEqual(filterVisits(fixture(),"","upcoming",token,now+1).map(v=>v.id),["future"]);
});
test("cancelled and rescheduled remain distinct; search combines with status",()=>{
  const visits=fixture();
  for(const status of ["completed","cancelled","missed"])assert.deepEqual(filterVisits(visits,"",status,token,now).map(v=>v.id),[status]);
  assert.deepEqual(filterVisits(visits,"anita","rescheduled",token,now).map(v=>v.id),["moved"]);
  assert.deepEqual(filterVisits(visits,"lim","rescheduled",token,now),[]);
});
test("filtering preserves original order and data, and follows refreshed status changes",()=>{
  const visits=fixture(),before=JSON.stringify(visits);
  filterVisits(visits,"lim","all",token,now);assert.equal(JSON.stringify(visits),before);
  const refreshed=visits.map(v=>v.id==="future"?{...v,status:"completed"}:v);
  assert.deepEqual(filterVisits(refreshed,"l001","upcoming",token,now),[]);
  assert.deepEqual(filterVisits(refreshed,"l001","completed",token,now).map(v=>v.id),["future"]);
  assert.deepEqual(filterVisits([],"","all",token,now),[]);
});
