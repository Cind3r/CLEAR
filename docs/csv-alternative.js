// Alternative CSV-based approach - much simpler!

async function queryHospitalCSV(csvPath, regexOrCode){
  if (!regexOrCode) return [];
  
  try {
    // Fetch and parse CSV
    const data = await d3.csv(csvPath);
    const regex = new RegExp(regexOrCode, 'i');
    
    // Filter and map results
    const matches = data
      .filter(d => regex.test(d.description || ''))
      .slice(0, 50)
      .map(d => ({
        description: d.description,
        code_1: d.code_1,
        estimated_amount: +d.estimated_amount,
        standard_charge_min: +d.standard_charge_min,
        standard_charge_max: +d.standard_charge_max
      }))
      .sort((a, b) => (a.estimated_amount || 0) - (b.estimated_amount || 0));
    
    return matches;
  } catch(e) {
    console.warn("CSV query failed:", csvPath, e);
    return [];
  }
}

// Then just change your hospital data to reference CSV files instead:
// parquet_path -> csv_path