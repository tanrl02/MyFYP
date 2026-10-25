import test from "node:test";
import assert from "node:assert/strict";
import {filterAssessmentHistory} from "./patientAssessmentFilter.ts";

test("assessment dates use Malaysia midnight, including month/year boundaries and explicit offsets",()=>{
  const items=[
    {id:"before",created_at:"2026-10-17T15:59:59.999Z"},
    {id:"midnight",created_at:"2026-10-17T16:00:00Z"},
    {id:"end",created_at:"2026-10-18T15:59:59.999Z"},
    {id:"next",created_at:"2026-10-18T16:00:00Z"},
    {id:"offset",created_at:"2026-10-18T00:00:00+08:00"},
    {id:"newYear",created_at:"2026-12-31T16:00:00Z"},
    {id:"invalid",created_at:"invalid"}
  ];
  assert.deepEqual(filterAssessmentHistory(items,"2026-10-18").map(n=>n.id),["midnight","end","offset"]);
  assert.deepEqual(filterAssessmentHistory(items,"2027-01-01").map(n=>n.id),["newYear"]);
  assert.deepEqual(filterAssessmentHistory(items,"2026-10-19").map(n=>n.id),["next"]);
});

test("clear, no matches and refreshed saved records preserve source order and data",()=>{
  const items=[{id:"later",created_at:"2026-10-18T10:00:00Z",symptoms:{body_area:"Arm"}},{id:"earlier",created_at:"2026-10-18T08:00:00Z"}];
  const original=JSON.stringify(items);
  assert.deepEqual(filterAssessmentHistory(items,"2026-10-18"),items);
  assert.deepEqual(filterAssessmentHistory(items,"2026-10-17"),[]);
  assert.deepEqual(filterAssessmentHistory(items,null),items);
  assert.notEqual(filterAssessmentHistory(items,null),items);
  const incoming={id:"new",created_at:"2026-10-19T01:00:00Z"};
  assert.deepEqual(filterAssessmentHistory([incoming,...items],"2026-10-18"),items);
  assert.deepEqual(filterAssessmentHistory([incoming,...items],null),[incoming,...items]);
  assert.deepEqual(filterAssessmentHistory([],"2026-10-18"),[]);
  assert.equal(JSON.stringify(items),original);
});
