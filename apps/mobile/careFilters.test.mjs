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
