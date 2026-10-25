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


test("assessment search matches body area or description with trimmed case-insensitive substrings",()=>{
  const items=[
    {id:"area",created_at:"2026-10-18T01:00:00Z",symptoms:{body_area:"Forearm",description:""}},
    {id:"description",created_at:"2026-10-18T02:00:00Z",symptoms:{body_area:"Leg",description:"Dry PATCH near elbow"}},
    {id:"legacy",created_at:"2026-10-18T03:00:00Z",symptoms:null,example_category:"forearm"},
    {id:"missing",created_at:"2026-10-18T04:00:00Z"}
  ];
  const before=JSON.stringify(items);
  assert.deepEqual(filterAssessmentHistory(items,null,"  FOREarm  ").map(n=>n.id),["area"]);
  assert.deepEqual(filterAssessmentHistory(items,null,"patch").map(n=>n.id),["description"]);
  assert.deepEqual(filterAssessmentHistory(items,null,"elbow").map(n=>n.id),["description"]);
  assert.deepEqual(filterAssessmentHistory(items,null,"not present"),[]);
  assert.deepEqual(filterAssessmentHistory(items,null,"   "),items);
  assert.deepEqual(filterAssessmentHistory(items,null,""),items);
  assert.equal(JSON.stringify(items),before);
});

test("assessment search combines with Malaysia saved date and follows refreshed symptom details",()=>{
  const items=[
    {id:"earlier",created_at:"2026-10-17T15:59:59Z",symptoms:{body_area:"Arm",description:"Fictional red patch"}},
    {id:"match",created_at:"2026-10-17T16:00:00Z",symptoms:{body_area:"Arm",description:"Fictional dry patch"}},
    {id:"other",created_at:"2026-10-18T01:00:00Z",symptoms:{body_area:"Leg",description:"Other text"}}
  ];
  const before=JSON.stringify(items);
  assert.deepEqual(filterAssessmentHistory(items,"2026-10-18","arm").map(n=>n.id),["match"]);
  assert.deepEqual(filterAssessmentHistory(items,"2026-10-18",""),items.slice(1));
  assert.deepEqual(filterAssessmentHistory(items,null,"patch"),items.slice(0,2));
  const refreshed=items.map(n=>n.id==="other"?{...n,symptoms:{body_area:"Arm",description:"Changed fictional text"}}:n);
  assert.deepEqual(filterAssessmentHistory(refreshed,"2026-10-18","arm").map(n=>n.id),["match","other"]);
  assert.deepEqual(filterAssessmentHistory([],null,"arm"),[]);
  assert.equal(JSON.stringify(items),before);
});
