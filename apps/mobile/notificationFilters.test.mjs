import test from "node:test";
import assert from "node:assert/strict";
import { filterNotifications } from "./patientNotificationFilter.ts";

test("read filters partition loaded notifications while preserving data and server order",()=>{
  const items=[{id:"a",read_at:null},{id:"b",read_at:"2032-10-25T01:00:00Z"},{id:"c",read_at:null}];
  const before=JSON.stringify(items);
  assert.deepEqual(filterNotifications(items,"all").map(n=>n.id),["a","b","c"]);
  assert.deepEqual(filterNotifications(items,"unread").map(n=>n.id),["a","c"]);
  assert.deepEqual(filterNotifications(items,"read").map(n=>n.id),["b"]);
  assert.equal(JSON.stringify(items),before);
});

test("refreshed read status and incoming notifications update membership without marking anything read",()=>{
  const items=[{id:"a",read_at:null},{id:"b",read_at:"2032-10-25T01:00:00Z"}];
  const refreshed=[{id:"new",read_at:null},...items.map(n=>n.id==="a"?{...n,read_at:"2032-10-25T02:00:00Z"}:n)];
  assert.deepEqual(filterNotifications(refreshed,"unread").map(n=>n.id),["new"]);
  assert.deepEqual(filterNotifications(refreshed,"read").map(n=>n.id),["a","b"]);
  assert.equal(items[0].read_at,null);
  assert.deepEqual(filterNotifications([items[1]],"unread"),[]);
  assert.deepEqual(filterNotifications([items[0]],"read"),[]);
  for(const status of ["all","unread","read"])assert.deepEqual(filterNotifications([],status),[]);
});


test("each notification type combines with read status without changing order or data",()=>{
  const kinds=["appointment_reminder","queue_called","review_published","follow_up_recommended","photo_follow_up_requested"];
  const items=kinds.flatMap(kind=>[{id:kind+"-read",kind,read_at:"2032-10-25T01:00:00Z"},{id:kind+"-unread",kind,read_at:null}]);
  const before=JSON.stringify(items);
  for(const kind of kinds){
    assert.deepEqual(filterNotifications(items,"all",kind).map(n=>n.id),[kind+"-read",kind+"-unread"]);
    assert.deepEqual(filterNotifications(items,"unread",kind).map(n=>n.id),[kind+"-unread"]);
    assert.deepEqual(filterNotifications(items,"read",kind).map(n=>n.id),[kind+"-read"]);
  }
  assert.equal(filterNotifications(items,"all","all").length,kinds.length*2);
  assert.equal(filterNotifications(items,"unread","all").length,kinds.length);
  assert.equal(JSON.stringify(items),before);
});

test("combined type filter handles absent types and refreshed read status",()=>{
  const items=[{id:"review",kind:"review_published",read_at:null},{id:"queue",kind:"queue_called",read_at:null}];
  assert.deepEqual(filterNotifications(items,"all","appointment_reminder"),[]);
  assert.deepEqual(filterNotifications(items,"read","review_published"),[]);
  const refreshed=[{id:"new",kind:"review_published",read_at:null},...items.map(n=>n.id==="review"?{...n,read_at:"2032-10-25T01:00:00Z"}:n)];
  assert.deepEqual(filterNotifications(refreshed,"unread","review_published").map(n=>n.id),["new"]);
  assert.deepEqual(filterNotifications(refreshed,"read","review_published").map(n=>n.id),["review"]);
  assert.deepEqual(filterNotifications(refreshed,"unread","queue_called").map(n=>n.id),["queue"]);
  assert.deepEqual(filterNotifications([],"all","follow_up_recommended"),[]);
});


test("search matches title or message with trimmed case-insensitive text and preserves source order",()=>{
  const items=[{id:"a",title:"Follow-up visit recommended",message:"L001 with Dr. Lim",kind:"follow_up_recommended",read_at:null},{id:"b",title:"Doctor review is ready",message:"Dr. Anita published a review",kind:"review_published",read_at:"2032-10-25T01:00:00Z"},{id:"c",title:"Queue called",message:"L001 with Dr. Lim",kind:"queue_called",read_at:null}];
  const before=JSON.stringify(items);
  const ids=query=>filterNotifications(items,"all","all",query).map(n=>n.id);
  assert.deepEqual(ids("  FOLLOW-UP  "),["a"]);
  assert.deepEqual(ids(" l001 "),["a","c"]);
  assert.deepEqual(ids("LIM"),["a","c"]);
  assert.deepEqual(ids("review"),["b"]);
  assert.deepEqual(ids("missing"),[]);
  assert.deepEqual(ids("  "),["a","b","c"]);
  assert.equal(JSON.stringify(items),before);
});

test("search combines with read/type filters and follows refreshed title/message/read changes",()=>{
  const items=[{id:"a",title:"Doctor review",message:"Dr. Lim",kind:"review_published",read_at:null},{id:"b",title:"Queue called",message:"Dr. Lim",kind:"queue_called",read_at:null}];
  assert.deepEqual(filterNotifications(items,"unread","review_published","lim").map(n=>n.id),["a"]);
  assert.deepEqual(filterNotifications(items,"read","review_published","lim"),[]);
  const refreshed=items.map(n=>n.id==="a"?{...n,read_at:"2032-10-25T01:00:00Z"}:n);
  assert.deepEqual(filterNotifications(refreshed,"unread","review_published","lim"),[]);
  assert.deepEqual(filterNotifications(refreshed,"read","review_published","lim").map(n=>n.id),["a"]);
  const changed=refreshed.map(n=>n.id==="a"?{...n,title:"Published assessment",message:"Dr. Anita"}:n);
  assert.deepEqual(filterNotifications(changed,"read","review_published","lim"),[]);
  assert.deepEqual(filterNotifications([],"all","all","lim"),[]);
});
