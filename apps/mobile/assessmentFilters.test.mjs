import test from "node:test";
import assert from "node:assert/strict";
import {filterAssessmentHistory,sortAssessmentHistory} from "./patientAssessmentFilter.ts";

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


test("assessment sorting normalises offsets, breaks ties by ID and puts invalid dates last without mutation",()=>{
  const items=[
    {id:"z",created_at:"2026-10-18T01:00:00Z"},
    {id:"a",created_at:"2026-10-18T09:00:00+08:00"},
    {id:"new",created_at:"2026-10-18T02:00:00Z"},
    {id:"old",created_at:"2026-10-17T01:00:00Z"},
    {id:"invalid",created_at:"invalid"}
  ];
  const before=JSON.stringify(items);
  assert.deepEqual(sortAssessmentHistory(items,"newest").map(n=>n.id),["new","a","z","old","invalid"]);
  assert.deepEqual(sortAssessmentHistory(items,"oldest").map(n=>n.id),["old","a","z","new","invalid"]);
  assert.deepEqual(sortAssessmentHistory([],"oldest"),[]);
  assert.equal(JSON.stringify(items),before);
});

test("assessment ordering respects combined search/date and refreshed saved times",()=>{
  const items=[
    {id:"new",created_at:"2026-10-18T04:00:00Z",symptoms:{body_area:"Arm",description:""}},
    {id:"old",created_at:"2026-10-17T16:00:00Z",symptoms:{body_area:"Arm",description:""}},
    {id:"other",created_at:"2026-10-18T03:00:00Z",symptoms:{body_area:"Leg",description:""}},
    {id:"previous",created_at:"2026-10-17T15:59:59Z",symptoms:{body_area:"Arm",description:""}}
  ];
  const filtered=filterAssessmentHistory(items,"2026-10-18","arm");
  assert.deepEqual(sortAssessmentHistory(filtered,"oldest").map(n=>n.id),["old","new"]);
  assert.deepEqual(sortAssessmentHistory(filtered,"newest").map(n=>n.id),["new","old"]);
  const refreshed=items.map(n=>n.id==="old"?{...n,created_at:"2026-10-18T05:00:00Z"}:n);
  assert.deepEqual(sortAssessmentHistory(filterAssessmentHistory(refreshed,"2026-10-18","arm"),"oldest").map(n=>n.id),["new","old"]);
  assert.deepEqual(filtered.map(n=>n.id),["new","old"]);
});


test("assessment source filters use saved origin metadata and preserve all-source records",()=>{
  const items=[
    {id:"ai",origin:"experimental_ai",created_at:"2026-10-18T01:00:00Z"},
    {id:"sim",origin:"simulation",created_at:"2026-10-18T02:00:00Z"},
    {id:"unknown",origin:"future_source",created_at:"2026-10-18T03:00:00Z"}
  ];
  const before=JSON.stringify(items);
  assert.deepEqual(filterAssessmentHistory(items,null,"","experimental_ai").map(n=>n.id),["ai"]);
  assert.deepEqual(filterAssessmentHistory(items,null,"","simulation").map(n=>n.id),["sim"]);
  assert.deepEqual(filterAssessmentHistory(items,null,"","all"),items);
  assert.deepEqual(filterAssessmentHistory(items,null),items);
  assert.deepEqual(filterAssessmentHistory([],null,"","simulation"),[]);
  assert.equal(JSON.stringify(items),before);
});

test("assessment source combines with search, Malaysia date, order and refreshed origin",()=>{
  const items=[
    {id:"new",origin:"experimental_ai",created_at:"2026-10-18T04:00:00Z",symptoms:{body_area:"Arm",description:""}},
    {id:"sim",origin:"simulation",created_at:"2026-10-18T03:00:00Z",symptoms:{body_area:"Arm",description:""}},
    {id:"old",origin:"experimental_ai",created_at:"2026-10-17T16:00:00Z",symptoms:{body_area:"Leg",description:"Arm test"}},
    {id:"previous",origin:"experimental_ai",created_at:"2026-10-17T15:59:59Z",symptoms:{body_area:"Arm",description:""}}
  ];
  const before=JSON.stringify(items);
  const filtered=filterAssessmentHistory(items,"2026-10-18","  ARM  ","experimental_ai");
  assert.deepEqual(sortAssessmentHistory(filtered,"oldest").map(n=>n.id),["old","new"]);
  assert.deepEqual(filterAssessmentHistory(items,"2026-10-18","arm","simulation").map(n=>n.id),["sim"]);
  assert.deepEqual(filterAssessmentHistory(items,"2026-10-18","missing","simulation"),[]);
  assert.deepEqual(filterAssessmentHistory(items,"2026-10-18","arm","all").map(n=>n.id),["new","sim","old"]);
  const refreshed=items.map(n=>n.id==="sim"?{...n,origin:"experimental_ai"}:n);
  assert.deepEqual(filterAssessmentHistory(refreshed,"2026-10-18","arm","simulation"),[]);
  assert.equal(JSON.stringify(items),before);
});


test("review filters include overlapping statuses and keep unknown counts only under All",()=>{
  const items=[
    {id:"published",review_summary:{published_reviews:2,awaiting_reviews:0}},
    {id:"awaiting",review_summary:{published_reviews:0,awaiting_reviews:1}},
    {id:"both",review_summary:{published_reviews:1,awaiting_reviews:2}},
    {id:"zero",review_summary:{published_reviews:0,awaiting_reviews:0}},
    {id:"unknown"}
  ];
  const before=JSON.stringify(items);
  assert.deepEqual(filterAssessmentHistory(items,null,"","all","published").map(n=>n.id),["published","both"]);
  assert.deepEqual(filterAssessmentHistory(items,null,"","all","awaiting").map(n=>n.id),["awaiting","both"]);
  assert.deepEqual(filterAssessmentHistory(items,null,"","all","all"),items);
  assert.deepEqual(filterAssessmentHistory([],null,"","all","awaiting"),[]);
  assert.equal(JSON.stringify(items),before);
});

test("review status combines with search, date, source, ordering and refreshed counts",()=>{
  const items=[
    {id:"new",origin:"experimental_ai",created_at:"2026-10-18T04:00:00Z",symptoms:{body_area:"Arm",description:""},review_summary:{published_reviews:1,awaiting_reviews:0}},
    {id:"old",origin:"experimental_ai",created_at:"2026-10-17T16:00:00Z",symptoms:{body_area:"Leg",description:"Arm test"},review_summary:{published_reviews:1,awaiting_reviews:1}},
    {id:"sim",origin:"simulation",created_at:"2026-10-18T03:00:00Z",symptoms:{body_area:"Arm",description:""},review_summary:{published_reviews:1,awaiting_reviews:0}},
    {id:"previous",origin:"experimental_ai",created_at:"2026-10-17T15:59:59Z",symptoms:{body_area:"Arm",description:""},review_summary:{published_reviews:1,awaiting_reviews:0}}
  ];
  const before=JSON.stringify(items);
  const filtered=filterAssessmentHistory(items,"2026-10-18","  ARM  ","experimental_ai","published");
  assert.deepEqual(sortAssessmentHistory(filtered,"oldest").map(n=>n.id),["old","new"]);
  assert.deepEqual(filterAssessmentHistory(items,"2026-10-18","arm","experimental_ai","awaiting").map(n=>n.id),["old"]);
  const refreshed=items.map(n=>n.id==="old"?{...n,review_summary:{published_reviews:2,awaiting_reviews:0}}:n);
  assert.deepEqual(filterAssessmentHistory(refreshed,"2026-10-18","arm","experimental_ai","awaiting"),[]);
  assert.deepEqual(filterAssessmentHistory(refreshed,"2026-10-18","arm","experimental_ai","published").map(n=>n.id),["new","old"]);
  assert.equal(JSON.stringify(items),before);
});
