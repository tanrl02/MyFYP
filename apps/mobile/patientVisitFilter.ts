import type {Booking} from "@smart-skin/shared";

export const visitFilterLabels={all:"All visits",upcoming:"Upcoming",completed:"Completed",cancelled:"Cancelled",missed:"Missed",rescheduled:"Rescheduled"} as const;
export type VisitFilter=keyof typeof visitFilterLabels;

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
