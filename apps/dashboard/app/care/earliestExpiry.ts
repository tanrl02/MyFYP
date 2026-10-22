import type {DispensingStock,PrescriptionItem} from "@smart-skin/shared";

export function earliestExpiryQuantities(items:Pick<PrescriptionItem,"medicine_id"|"quantity">[],stock:DispensingStock,asOf=new Date(Date.now()+8*3600000).toISOString().slice(0,10)){
  const quantities:Record<string,string>={};
  for(const item of items){
    const current=stock.items.find(source=>source.medicine_id===item.medicine_id);
    // Explicit zeros replace manual choices and suppress the form's untracked default.
    quantities[`${item.medicine_id}|`]="0";
    for(const batch of current?.batches??[])quantities[`${item.medicine_id}|${batch.receipt_id}`]="0";
    let needed=Math.min(item.quantity,current?.stock??0);
    const batches=[...(current?.batches??[])].filter(batch=>!batch.expired&&batch.expiry_date>=asOf&&batch.remaining_units>0)
      .sort((a,b)=>a.expiry_date.localeCompare(b.expiry_date)||a.receipt_id.localeCompare(b.receipt_id));
    for(const batch of batches){
      if(needed<=0)break;
      const quantity=Math.min(needed,batch.remaining_units);
      quantities[`${item.medicine_id}|${batch.receipt_id}`]=String(quantity);
      needed-=quantity;
    }
  }
  return quantities;
}
