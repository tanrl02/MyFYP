import test from "node:test";
import assert from "node:assert/strict";
import {filterCare} from "./patientCareFilter.ts";

const record=(id,prescription=null,invoice=null)=>({visit:{id},prescription:prescription?{status:prescription}:null,invoice:invoice?{status:invoice}:null});
test("care statuses distinguish issued prescriptions and actual invoice states",()=>{
  const records=[record("empty"),record("issued","issued"),record("issued-bill","issued","unpaid"),record("dispensed","dispensed"),record("unpaid","dispensed","unpaid"),record("paid","dispensed","paid"),record("bill-only",null,"unpaid")];
  const ids=status=>filterCare(records,status).map(r=>r.visit.id);
  assert.deepEqual(ids("all"),["issued","issued-bill","dispensed","unpaid","paid","bill-only"]);
  assert.deepEqual(ids("dispensing"),["issued","issued-bill"]);
  assert.deepEqual(ids("unpaid"),["issued-bill","unpaid","bill-only"]);
  assert.deepEqual(ids("paid"),["paid"]);
});
test("refresh transitions update membership without altering records or their order",()=>{
  const records=[record("a","issued"),record("b","dispensed","unpaid")];
  const before=JSON.stringify(records);
  filterCare(records,"unpaid"); assert.equal(JSON.stringify(records),before);
  const refreshed=[record("a","dispensed","unpaid"),record("b","dispensed","paid")];
  assert.deepEqual(filterCare(refreshed,"dispensing"),[]);
  assert.deepEqual(filterCare(refreshed,"unpaid").map(r=>r.visit.id),["a"]);
  assert.deepEqual(filterCare(refreshed,"paid").map(r=>r.visit.id),["b"]);
  assert.deepEqual(filterCare([],"all"),[]);
});

test("search matches displayed doctor or token and combines with status without changing source",()=>{
  const records=[record("a","issued"),record("b","dispensed","paid"),record("c",null,"unpaid"),record("empty")].map((r,i)=>({...r,visit:{...r.visit,doctor_name:i<2?"Dr. Lim (demo)":"Dr. Anita (demo)",token:i<2?"L001":"A002"}}));
  const token=visit=>visit.token;
  const before=JSON.stringify(records);
  const ids=(status,query)=>filterCare(records,status,query,token).map(r=>r.visit.id);
  assert.deepEqual(ids("all","  lIm  "),["a","b"]);
  assert.deepEqual(ids("paid"," l001 "),["b"]);
  assert.deepEqual(ids("dispensing","L001"),["a"]);
  assert.deepEqual(ids("unpaid","ANITA"),["c"]);
  assert.deepEqual(ids("paid","Anita"),[]);
  assert.deepEqual(ids("all","missing"),[]);
  assert.deepEqual(ids("all","   "),["a","b","c"]);
  assert.equal(JSON.stringify(records),before);
  const refreshed=records.map(r=>r.visit.id==="a"?{...r,visit:{...r.visit,doctor_name:"Dr. Other",token:"O003"}}:r);
  assert.deepEqual(filterCare(refreshed,"all","l001",token).map(r=>r.visit.id),["b"]);
  assert.deepEqual(filterCare([],"all","lim",token),[]);
});

test("appointment date uses saved Malaysia clinic date and combines with search and status",()=>{
  const records=[record("a","dispensed","paid"),record("b","dispensed","paid"),record("c","issued"),record("empty")].map((r,i)=>({...r,visit:{...r.visit,doctor_name:"Dr. Lim",token:"L001",clinic_date:i===1?"2032-10-23":"2032-10-24",starts_at:"2032-10-23T16:00:00Z"}}));
  const token=visit=>visit.token;
  const before=JSON.stringify(records);
  const ids=(status,query,date)=>filterCare(records,status,query,token,date).map(r=>r.visit.id);
  assert.deepEqual(ids("paid"," l001 ","2032-10-24"),["a"]);
  assert.deepEqual(ids("paid","LIM","2032-10-23"),["b"]);
  assert.deepEqual(ids("dispensing","lim","2032-10-24"),["c"]);
  assert.deepEqual(ids("all","","2032-10-25"),[]);
  assert.deepEqual(ids("paid","l001",null),["a","b"]);
  assert.deepEqual(ids("all","",null),["a","b","c"]);
  assert.equal(JSON.stringify(records),before);
  const refreshed=records.map(r=>r.visit.id==="a"?{...r,visit:{...r.visit,clinic_date:"2032-10-25"}}:r);
  assert.deepEqual(filterCare(refreshed,"paid","l001",token,"2032-10-24"),[]);
  assert.deepEqual(filterCare([],"all","",token,"2032-10-24"),[]);
});
