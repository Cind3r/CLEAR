// Alternative: Pure Apache Arrow approach (most reliable)
// Replace the import with:
import * as Arrow from "https://cdn.jsdelivr.net/npm/apache-arrow@17/+esm";

// Alternative query function using just Arrow (no parquet dependencies):
async function queryHospitalParquet(relPath, regexOrCode){
  if (!regexOrCode) return [];
  const url = parquetUrl(relPath);
  
  try {
    // Fetch the parquet file as binary
    const response = await fetch(url);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const buffer = await response.arrayBuffer();
    
    // Try to read with Arrow (works if server can convert parquet to arrow)
    const table = Arrow.tableFromIPC(buffer);
    const regex = new RegExp(regexOrCode, 'i');
    
    const records = [];
    for (let i = 0; i < table.numRows; i++) {
      const description = table.get(i).description || '';
      
      if (regex.test(description)) {
        const row = table.get(i);
        records.push({
          description: row.description,
          code_1: row.code_1,
          estimated_amount: row.estimated_amount,
          standard_charge_min: row.standard_charge_min,
          standard_charge_max: row.standard_charge_max
        });
      }
      
      if (records.length >= 50) break;
    }
    
    return records.sort((a, b) => (a.estimated_amount || 0) - (b.estimated_amount || 0));
  } catch(e){
    console.warn("Parquet query failed:", url, e);
    return [];
  }
}