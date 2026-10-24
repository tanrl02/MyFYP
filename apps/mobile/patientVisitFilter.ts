import type {Booking} from "@smart-skin/shared";

export const visitFilterLabels={all:"All visits",upcoming:"Upcoming",completed:"Completed",cancelled:"Cancelled",missed:"Missed",rescheduled:"Rescheduled"} as const;
export type VisitFilter=keyof typeof visitFilterLabels;
export const visitOrderLabels={newest:"Newest first",oldest:"Oldest first"} as const;
export type VisitOrder=keyof typeof visitOrderLabels;

export function sortVisits(bookings:Booking[],order:VisitOrder):Booking[]{
  return [...bookings].sort((a,b)=>{
    const difference=Date.parse(a.starts_at)-Date.parse(b.starts_at);
    if(Number.isFinite(difference)&&difference!==0)return order==="oldest"?difference:-difference;
    return a.queue_number-b.queue_number || (a.id<b.id?-1:a.id>b.id?1:0);
  });
}

export function filterVisits(bookings:Booking[],query:string,status:VisitFilter,token:(booking:Booking)=>string,date:string|null=null,now=Date.now()):Booking[]{
  const search=query.trim().toLocaleLowerCase();
  return bookings.filter(visit=>{
    if(date && visit.clinic_date!==date)return false;
    if(search && !visit.doctor_name.toLocaleLowerCase().includes(search) && !token(visit).toLocaleLowerCase().includes(search))return false;
    if(status==="all")return true;
    if(status==="rescheduled")return !!visit.rescheduled_to_id;
    if(visit.rescheduled_to_id)return false;
    if(status==="upcoming")return (visit.status==="waiting"||visit.status==="called") && Date.parse(visit.starts_at)>=now;
    return visit.status===status;
  });
}
