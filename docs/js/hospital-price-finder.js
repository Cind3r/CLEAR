/**
 * Hospital Price Finder - Main Application JavaScript
 * 
 * This file contains all the functionality for the Hospital Price Finder application,
 * including map visualization, data loading, price searching, and visualization charts.
 * 
 * Main Functions Exported:
 * - Mobile device detection and redirect
 * - Map visualization with D3.js
 * - Hospital search and filtering
 * - Price data loading and display
 * - Interactive visualizations (histogram and slope charts)
 * - Configuration management for services and revenue codes
 * 
 * Dependencies:
 * - D3.js v7 (loaded via CDN)
 * - Topojson (loaded via CDN)
 */

// Import required modules
import * as topojson from "https://cdn.jsdelivr.net/npm/topojson-client@3/+esm";

// ========================================
// MOBILE DEVICE DETECTION AND REDIRECT
// ========================================

/**
 * Detects mobile devices and redirects to mobile version
 * Checks user agent, screen size, and touch capability
 */
(function() {
  // Check if user is on mobile device
  const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
  const isSmallScreen = window.innerWidth <= 768;
  const hasTouch = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
  
  // Redirect to mobile version if mobile device detected
  if ((isMobile || (isSmallScreen && hasTouch)) && !window.location.search.includes('desktop=1')) {
    window.location.href = 'index-mobile.html';
  }
})();

// ========================================
// APPLICATION CONFIGURATION AND CONSTANTS
// ========================================

// Map and geographic constants
const WIDTH = 960, HEIGHT = 600, EARTH_MI = 3958.7613;
const ENABLE_PRICES = true;  // set false to debug map/CSV only

// Data file paths - robust path resolution relative to this HTML file
const urlFrom = (p) => p;  // Simple relative path resolution
const DATA_ZIPS = "data/zip_centroids.csv";
const DATA_HOSPS = "data/hospitals.csv";
const DATA_SERVICE = "data/service_config.json";
const DATA_RC = "data/rc_config.json";
const DATA_CMS = "data/medicare_pricing_matched.csv";
const jsonUrl = (relPath) => relPath.startsWith('docs/') ? relPath.substring(5) : relPath;

// ========================================
// DOM ELEMENT REFERENCES
// ========================================

/**
 * Get references to all important DOM elements
 * These are used throughout the application for user interaction
 */
const svg = d3.select("#map");
const $q = document.getElementById("q");
const $zip = document.getElementById("zip");
const $radius = document.getElementById("radius");
const $payer = document.getElementById("payer");
const $service = document.getElementById("service");
const $configType = document.getElementById("config-type");
const $unit = document.getElementById("unit");
const $go = document.getElementById("go");
const $status = document.getElementById("status");
const $list = document.getElementById("list");
const $listTitle = document.getElementById("list-title");

/**
 * Updates the status message displayed to the user
 * @param {string} t - Status message text
 */
const setStatus = (t) => $status.textContent = t;

// ========================================
// DATA STORAGE AND CONFIGURATION
// ========================================

// Data maps for storing loaded configurations and pricing data
const cmsRate = new Map();           // Medicare pricing rates
const services = new Map();          // Service configuration patterns
const revenueCodes = new Map();      // Revenue code configuration patterns
let currentConfigType = 'service';   // Current configuration type (service or revenue-code)

// ========================================
// MAP SETUP AND VISUALIZATION
// ========================================

/**
 * Initialize D3 map projection and zoom functionality
 * Sets up the base map with states, graticule, and interactive elements
 */
const projection = d3.geoAlbersUsa().translate([WIDTH/2, HEIGHT/2]).scale(1200);
const path = d3.geoPath(projection);
const gBase = svg.append("g");       // Base layer for map features
const gOverlay = svg.append("g");    // Overlay layer for interactive elements

/**
 * Zoom behavior configuration
 * Disables mouse wheel zoom but allows drag and programmatic zoom
 */
const zoom = d3.zoom().scaleExtent([1, 20])
  .filter(event => {
    // Disable mouse wheel zoom, but allow other interactions (drag, programmatic)
    return !event.ctrlKey && event.type !== 'wheel';
  })
  .on("zoom", (ev) => {
    gBase.attr("transform", ev.transform);
    gOverlay.attr("transform", ev.transform);
    gOverlay.selectAll(".marker-zip").attr("r", 4/ev.transform.k);
    gOverlay.selectAll(".marker-hosp").attr("r", 3.5/ev.transform.k);
  });
svg.call(zoom);

/**
 * Reset zoom button functionality
 * Returns map to original zoom level and position
 */
document.getElementById('reset-zoom').addEventListener('click', () => {
  svg.transition().duration(800)
     .call(zoom.transform, d3.zoomIdentity);
});

// Map overlay elements
const circlePath = gOverlay.append("path").attr("class","circle").style("display","none");
const zipMarker  = gOverlay.append("circle").attr("class","marker-zip").attr("r",4).style("display","none");
const hospLayer  = gOverlay.append("g").attr("class","hospitals");

// ========================================
// GEOGRAPHIC AND MATH UTILITIES
// ========================================

/**
 * Convert miles to degrees for geographic calculations
 * @param {number} mi - Distance in miles
 * @returns {number} Distance in degrees
 */
const miles2deg = (mi) => mi/69;

/**
 * Calculate great circle distance between two coordinate points
 * @param {Array} aLonLat - [longitude, latitude] of first point
 * @param {Array} bLonLat - [longitude, latitude] of second point
 * @returns {number} Distance in miles
 */
const gcMiles = (aLonLat, bLonLat) => d3.geoDistance(aLonLat, bLonLat) * EARTH_MI;

/**
 * Zoom to a specific geographic feature with padding
 * @param {Object} feature - GeoJSON feature to zoom to
 * @param {number} pad - Padding around the feature in pixels
 */
function zoomTo(feature, pad=20){
  const [[x0,y0],[x1,y1]] = path.bounds(feature);
  const dx=x1-x0, dy=y1-y0, cx=(x0+x1)/2, cy=(y0+y1)/2;
  const scale = Math.max(1, Math.min(20, 0.9/Math.max(dx/(WIDTH-2*pad), dy/(HEIGHT-2*pad))));
  const translate = [WIDTH/2 - scale*cx, HEIGHT/2 - scale*cy];
  svg.transition().duration(800)
     .call(zoom.transform, d3.zoomIdentity.translate(translate[0], translate[1]).scale(scale));
}

// ========================================
// DATA LOADING AND INITIALIZATION
// ========================================

/**
 * Load and initialize the base map with US states and graticule
 * Handles errors gracefully and updates status
 */
async function initializeBasemap() {
  try {
    const graticule = d3.geoGraticule10();
    gBase.append("path").attr("class","graticule").attr("d", path(graticule));
    const res = await fetch("https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json");
    if (!res.ok) throw new Error(`us-atlas fetch failed: ${res.status}`);
    const us = await res.json();
    const states = topojson.feature(us, us.objects.states).features;
    gBase.selectAll("path.state").data(states).join("path").attr("class","state").attr("d", path);
  } catch (err) {
    console.error("Basemap error:", err);
    setStatus("Basemap failed to load. See console.");
  }
}

/**
 * Load ZIP code centroids data
 * @returns {Map} Map of ZIP codes to [lat, lon] coordinates
 */
async function loadZipData() {
  try {
    const zipRows = await d3.csv(DATA_ZIPS, d3.autoType);
    return new Map(zipRows.map(d=>[String(d.zip).padStart(5,'0'), [d.lat, d.lon]]));
  } catch (e) {
    console.warn("zip_centroids.csv failed:", e);
    setStatus("ZIP data missing.");
    return new Map();
  }
}

/**
 * Load hospital directory data
 * @returns {Array} Array of hospital objects with location data
 */
async function loadHospitalData() {
  try {
    const hospitals = await d3.csv(DATA_HOSPS, d3.autoType);
    hospitals.forEach(d => { 
      d.ll = [d.lon, d.lat]; 
      // Use json_path from CSV
      d.json_path = d.json_path || '';
    });
    return hospitals;
  } catch (e) {
    console.warn("hospitals.csv failed:", e);
    setStatus("Hospitals index missing.");
    return [];
  }
}

/**
 * Load service configuration patterns
 * @returns {Map} Map of service names to regex patterns
 */
async function loadServiceConfig() {
  try {
    const svcCfg = await fetch(DATA_SERVICE).then(r=>r.json());
    const serviceMap = new Map();
    Object.entries(svcCfg).forEach(([name, obj])=>{
      serviceMap.set(name, new RegExp(obj.pattern, 'i'));
    });
    return serviceMap;
  } catch (e) {
    console.warn("service_config.json failed:", e);
    return new Map();
  }
}

/**
 * Load revenue code configuration patterns
 * @returns {Map} Map of revenue code names to regex patterns
 */
async function loadRevenueCodeConfig() {
  try {
    const rcCfg = await fetch(DATA_RC).then(r=>r.json());
    const rcMap = new Map();
    Object.entries(rcCfg).forEach(([name, obj])=>{
      rcMap.set(name, new RegExp(obj.pattern, 'i'));
    });
    return rcMap;
  } catch (e) {
    console.warn("rc_config.json failed:", e);
    return new Map();
  }
}

/**
 * Load Medicare pricing data for ratio calculations
 * @returns {Map} Map of procedure codes to Medicare rates
 */
async function loadMedicareRates() {
  try {
    const cmsRows = await d3.csv(DATA_CMS, d3.autoType);
    const rateMap = new Map();
    cmsRows.forEach(r => rateMap.set(String(r.code), +r.price || 0));
    return rateMap;
  } catch (e) {
    console.warn("medicare_pricing_matched.csv failed:", e);
    return new Map();
  }
}

// ========================================
// CONFIGURATION MANAGEMENT
// ========================================

/**
 * Populate the service/revenue code dropdown based on configuration type
 * @param {string} configType - Either 'service' or 'revenue-code'
 */
function populateServiceDropdown(configType) {
  // Clear existing options except the first one
  $service.innerHTML = '<option value="">(Select Group)</option>';
  
  const configMap = configType === 'service' ? services : revenueCodes;
  
  configMap.forEach((regex, name) => {
    const opt = document.createElement('option'); 
    opt.value = name; 
    opt.textContent = name;
    $service.appendChild(opt);
  });
  
  // Add Custom Pattern option at the end
  const customOpt = document.createElement('option');
  customOpt.value = 'custom';
  customOpt.textContent = 'Custom Pattern';
  $service.appendChild(customOpt);
}

/**
 * Handle configuration type change (service vs revenue code)
 */
function handleConfigTypeChange() {
  currentConfigType = $configType.value;
  populateServiceDropdown(currentConfigType);
  
  // Reset service selection
  $service.value = '';
  // Hide procedure input
  document.getElementById('procedure-label').style.display = 'none';
  $q.value = '';
}

/**
 * Handle service selection change
 * Shows/hides custom pattern input based on selection
 */
function handleServiceChange() {
  const procedureLabel = document.getElementById('procedure-label');
  if ($service.value === 'custom') {
    // Show search bar for custom pattern
    procedureLabel.style.display = '';
    $q.placeholder = "e.g. (MRI|70551)|^70551$";
    $q.value = '';
  } else if ($service.value) {
    // Hide search bar for predefined services
    procedureLabel.style.display = 'none';
    $q.value = ''; // Clear custom pattern when service is selected
  } else {
    // Hide search bar when no selection
    procedureLabel.style.display = 'none';
    $q.value = '';
  }
}

// ========================================
// PRICE DATA UTILITIES
// ========================================

/**
 * Extract a usable dollar amount from a record
 * @param {Object} r - Price record with various amount fields
 * @returns {number} Best available dollar amount
 */
const amountOf = r => +r.estimated_amount || +r.standard_charge_dollar || +r.standard_charge_gross
                  || +r.standard_charge_min || +r.standard_charge_max || 0;

/**
 * Format price display with Medicare ratio calculation
 * @param {number} amount - Dollar amount to format
 * @param {string} code - Procedure code for Medicare ratio lookup
 * @returns {Object} Object with formatted price and ratio strings
 */
const formatPrice = (amount, code) => {
  if (!amount || amount === 0) return { price: "N/A", ratio: "N/A" };
  
  const price = `$${Number(amount).toLocaleString()}`;
  let ratio = "N/A";
  
  if (code) {
    const medicareRate = cmsRate.get(String(code)) || 0;
    if (medicareRate > 0) {
      ratio = `${(amount / medicareRate).toFixed(2)}x`;
    }
  }
  
  return { price, ratio };
};

/**
 * Get the appropriate code field for display and Medicare calculations
 * @param {Object} record - Price record
 * @returns {string} Code value for display
 */
const getCodeField = (record) => {
  // Always use 'code' field for display and Medicare ratio calculations
  return record.code || '';
};

/**
 * Get the search code field based on configuration type
 * @returns {string} Field name to search in ('code' or 'rc_code')
 */
const getSearchCodeField = () => {
  return currentConfigType === 'service' ? 'code' : 'rc_code';
};

/**
 * Generate HTML table for price display
 * @param {Object} record - Price record with multiple price types
 * @returns {string} HTML table string
 */
const generatePriceTable = (record) => {
  const showRatio = $unit.checked;
  const code = getCodeField(record);
  const priceTypes = [];
  
  if (record.estimated_amount != null) {
    const formatted = formatPrice(record.estimated_amount, code);
    priceTypes.push({ type: "Estimate", price: formatted.price, ratio: formatted.ratio });
  }
  if (record.standard_charge_min != null) {
    const formatted = formatPrice(record.standard_charge_min, code);
    priceTypes.push({ type: "Minimum", price: formatted.price, ratio: formatted.ratio });
  }
  if (record.standard_charge_max != null) {
    const formatted = formatPrice(record.standard_charge_max, code);
    priceTypes.push({ type: "Maximum", price: formatted.price, ratio: formatted.ratio });
  }
  
  if (priceTypes.length === 0) return "<div class='small'>No pricing data available</div>";
  
  return `
    <table class="price-table">
      <thead>
        <tr>
          <th></th>
          <th>Price</th>
          ${showRatio ? '<th>Medicare Ratio</th>' : ''}
        </tr>
      </thead>
      <tbody>
        ${priceTypes.map(pt => `
          <tr>
            <td class="price-type">${pt.type}</td>
            <td>${pt.price}</td>
            ${showRatio ? `<td>${pt.ratio}</td>` : ''}
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
};

// ========================================
// JSON DATA LOADING AND CACHING
// ========================================

// Cache for loaded JSON files to avoid repeated loading
const jsonCache = new Map();

/**
 * Load hospital JSON pricing data with caching
 * @param {string} jsonPath - Path to the JSON file
 * @returns {Array} Array of price records
 */
async function loadHospitalJSON(jsonPath) {
  if (!jsonPath) return [];
  
  try {
    // Check cache first
    if (jsonCache.has(jsonPath)) {
      return jsonCache.get(jsonPath);
    }
    
    // Load JSON file
    const url = jsonUrl(jsonPath);
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    const text = await response.text();
    // Parse JSON lines format (each line is a separate JSON object)
    const jsonData = text.trim().split('\n').map(line => {
      try {
        return JSON.parse(line);
      } catch (e) {
        console.warn("Failed to parse JSON line:", line.substring(0, 100));
        return null;
      }
    }).filter(obj => obj !== null);
    
    // Cache the parsed data
    jsonCache.set(jsonPath, jsonData);
    return jsonData;
    
  } catch(e) {
    console.warn("JSON loading failed:", jsonPath, e);
    return [];
  }
}

/**
 * Query hospital JSON data for matching procedures
 * @param {string} jsonPath - Path to the JSON file
 * @param {string} regexOrCode - Search pattern (regex or exact code)
 * @param {string} selectedPayer - Optional payer filter
 * @returns {Array} Array of matching price records
 */
async function queryHospitalJSON(jsonPath, regexOrCode, selectedPayer = null){
  if (!jsonPath || !regexOrCode) return [];
  
  try {
    const jsonData = await loadHospitalJSON(jsonPath);
    
    // Create regex for searching
    const regex = new RegExp(regexOrCode, 'i');
    
    // Determine which code field to search based on configuration type
    const codeField = getSearchCodeField();
    
    // Search through descriptions and codes
    let matches = jsonData.filter(record => {
      const description = record.description || '';
      const code = record[codeField] || '';
      const matchesRegex = regex.test(description) || regex.test(code);
      const matchesPayer = !selectedPayer || (record.payer_name && record.payer_name === selectedPayer);
      return matchesRegex && matchesPayer;
    }).slice(0, 50); // Limit to 50 results
    
    // Sort by estimated_amount if available
    matches.sort((a, b) => {
      const aAmount = parseFloat(a.estimated_amount) || 0;
      const bAmount = parseFloat(b.estimated_amount) || 0;
      return aAmount - bAmount;
    });
    
    return matches;
    
  } catch(e){
    console.warn("JSON query failed:", jsonPath, e);
    return [];
  }
}

// ========================================
// PAYER MANAGEMENT
// ========================================

/**
 * Extract unique payers from hospital JSON files
 * @param {Array} hospitalList - List of hospitals to check
 * @returns {Array} Sorted array of unique payer names
 */
async function getUniquePayers(hospitalList) {
  const payerSet = new Set();
  
  // Load all JSON files for hospitals in the list and extract unique payers
  const promises = hospitalList.map(async (hospital) => {
    if (!hospital.json_path) return;
    
    try {
      const jsonData = await loadHospitalJSON(hospital.json_path);
      jsonData.forEach(record => {
        if (record.payer_name && record.payer_name.trim()) {
          payerSet.add(record.payer_name.trim());
        }
      });
    } catch (e) {
      console.warn("Failed to load payers from:", hospital.json_path);
    }
  });
  
  await Promise.all(promises);
  
  // Convert set to sorted array
  return Array.from(payerSet).sort();
}

/**
 * Populate the payer dropdown with unique payers from search results
 * @param {Array} payers - Array of payer names
 */
function populatePayerDropdown(payers) {
  // Save the currently selected payer
  const currentSelection = $payer.value;
  
  // Clear existing options except "All Payers"
  $payer.innerHTML = '<option value="">All Payers</option>';
  
  // Add unique payers
  payers.forEach(payer => {
    const option = document.createElement('option');
    option.value = payer;
    option.textContent = payer;
    $payer.appendChild(option);
  });
  
  // Restore the previous selection if it still exists in the new list
  if (currentSelection && payers.includes(currentSelection)) {
    $payer.value = currentSelection;
  }
}

// ========================================
// VISUALIZATION COMPONENTS
// ========================================

// SVG elements for visualizations
const distributionSvg = d3.select("#distribution-chart");
const slopegraphSvg = d3.select("#slopegraph-chart");

/**
 * Create price distribution histogram visualization
 * @param {Array} allHits - All price records to visualize
 */
function createDistributionChart(allHits) {
  distributionSvg.selectAll("*").remove();
  
  if (!allHits || allHits.length === 0) {
    distributionSvg.append("text")
      .attr("x", "50%")
      .attr("y", "50%")
      .attr("text-anchor", "middle")
      .attr("fill", "#94a3b8")
      .text("No data to display");
    return;
  }

  const margin = {top: 20, right: 30, bottom: 40, left: 60};
  const containerWidth = parseInt(distributionSvg.style("width")) || 400;
  const containerHeight = parseInt(distributionSvg.style("height")) || 300;
  const width = containerWidth - margin.left - margin.right;
  const height = containerHeight - margin.top - margin.bottom;

  const g = distributionSvg.append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  // Get all price values
  const prices = [];
  allHits.forEach(hit => {
    if (hit.estimated_amount != null) prices.push(+hit.estimated_amount);
    if (hit.standard_charge_min != null) prices.push(+hit.standard_charge_min);
    if (hit.standard_charge_max != null) prices.push(+hit.standard_charge_max);
  });

  if (prices.length === 0) {
    g.append("text")
      .attr("x", width/2)
      .attr("y", height/2)
      .attr("text-anchor", "middle")
      .attr("fill", "#94a3b8")
      .text("No price data available");
    return;
  }

  // Create histogram
  const xScale = d3.scaleLinear()
    .domain(d3.extent(prices))
    .range([0, width]);

  const histogram = d3.histogram()
    .value(d => d)
    .domain(xScale.domain())
    .thresholds(Math.min(20, Math.ceil(Math.sqrt(prices.length))));

  const bins = histogram(prices);

  const yScale = d3.scaleLinear()
    .domain([0, d3.max(bins, d => d.length)])
    .range([height, 0]);

  // Add bars
  g.selectAll("rect")
    .data(bins)
    .join("rect")
    .attr("class", "distribution-bar")
    .attr("x", d => xScale(d.x0))
    .attr("width", d => Math.max(0, xScale(d.x1) - xScale(d.x0) - 1))
    .attr("y", d => yScale(d.length))
    .attr("height", d => height - yScale(d.length))
    .append("title")
    .text(d => `$${d.x0.toLocaleString()} - $${d.x1.toLocaleString()}: ${d.length} prices`);

  // Add axes
  g.append("g")
    .attr("class", "axis")
    .attr("transform", `translate(0,${height})`)
    .call(d3.axisBottom(xScale).tickFormat(d => `$${d/1000}k`));

  g.append("g")
    .attr("class", "axis")
    .call(d3.axisLeft(yScale));

  // Add labels
  g.append("text")
    .attr("x", width/2)
    .attr("y", height + 35)
    .attr("text-anchor", "middle")
    .attr("fill", "#e2e8f0")
    .style("font-size", "11px")
    .text($unit.checked ? "Price Distribution (All Types)" : "Price Distribution");

  g.append("text")
    .attr("transform", "rotate(-90)")
    .attr("y", -40)
    .attr("x", -height/2)
    .attr("text-anchor", "middle")
    .attr("fill", "#e2e8f0")
    .style("font-size", "11px")
    .text("Count");
}

/**
 * Create slopegraph visualization comparing min vs max prices by hospital
 * @param {Array} hospitalData - Hospital data with price hits
 */
function createSlopegraph(hospitalData) {
  slopegraphSvg.selectAll("*").remove();
  
  if (!hospitalData || hospitalData.length === 0) {
    slopegraphSvg.append("text")
      .attr("x", "50%")
      .attr("y", "50%")
      .attr("text-anchor", "middle")
      .attr("fill", "#94a3b8")
      .text("No data to display");
    return;
  }

  const margin = {top: 20, right: 80, bottom: 40, left: 80};
  const containerWidth = parseInt(slopegraphSvg.style("width")) || 400;
  const containerHeight = parseInt(slopegraphSvg.style("height")) || 300;
  const width = containerWidth - margin.left - margin.right;
  const height = containerHeight - margin.top - margin.bottom;

  const g = slopegraphSvg.append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  // Prepare data - get hospitals with both min and max prices
  const slopeData = hospitalData.filter(h => {
    const hits = h.hits || [];
    const minPrices = hits.filter(hit => hit.standard_charge_min != null);
    const maxPrices = hits.filter(hit => hit.standard_charge_max != null);
    return minPrices.length > 0 && maxPrices.length > 0;
  }).slice(0, 10); // Limit to 10 hospitals for readability

  if (slopeData.length === 0) {
    g.append("text")
      .attr("x", width/2)
      .attr("y", height/2)
      .attr("text-anchor", "middle")
      .attr("fill", "#94a3b8")
      .text("No min/max price data available");
    return;
  }

  // Calculate averages for each hospital
  const processedData = slopeData.map(h => {
    const hits = h.hits || [];
    const minPrices = hits.filter(hit => hit.standard_charge_min != null).map(hit => +hit.standard_charge_min);
    const maxPrices = hits.filter(hit => hit.standard_charge_max != null).map(hit => +hit.standard_charge_max);
    
    return {
      hospital: h.name,
      minAvg: d3.mean(minPrices),
      maxAvg: d3.mean(maxPrices)
    };
  }).filter(d => d.minAvg != null && d.maxAvg != null);

  if (processedData.length === 0) return;

  // Scales
  const allValues = processedData.flatMap(d => [d.minAvg, d.maxAvg]);
  const yScale = d3.scaleLinear()
    .domain(d3.extent(allValues))
    .range([height, 0]);

  // Color scale for different hospitals
  const colorScale = d3.scaleOrdinal()
    .domain(processedData.map(d => d.hospital))
    .range(d3.schemeCategory10);

  const xPositions = [0, width];

  // Create tooltip div for hospital names
  const tooltip = d3.select("body").selectAll(".slope-tooltip").data([0]).join("div")
    .attr("class", "slope-tooltip")
    .style("position", "absolute")
    .style("background", "rgba(15, 23, 42, 0.95)")
    .style("color", "#e2e8f0")
    .style("padding", "8px 12px")
    .style("border-radius", "6px")
    .style("border", "1px solid #374151")
    .style("font-size", "12px")
    .style("pointer-events", "none")
    .style("opacity", 0)
    .style("z-index", 1000);

  // Draw lines with hover functionality
  g.selectAll(".slope-line")
    .data(processedData)
    .join("path")
    .attr("d", d => d3.line()([[xPositions[0], yScale(d.minAvg)], [xPositions[1], yScale(d.maxAvg)]]))
    .style("stroke", d => colorScale(d.hospital))
    .style("stroke-width", "3px")
    .style("fill", "none")
    .style("opacity", 0.7)
    .style("cursor", "pointer")
    .on("mouseover", function(event, d) {
      d3.select(this).style("opacity", 1).style("stroke-width", "4px");
      tooltip
        .style("opacity", 1)
        .html(`<strong>${d.hospital}</strong><br/>Min: $${Math.round(d.minAvg).toLocaleString()}<br/>Max: $${Math.round(d.maxAvg).toLocaleString()}`)
        .style("left", (event.pageX + 10) + "px")
        .style("top", (event.pageY - 10) + "px");
    })
    .on("mousemove", function(event) {
      tooltip
        .style("left", (event.pageX + 10) + "px")
        .style("top", (event.pageY - 10) + "px");
    })
    .on("mouseout", function() {
      d3.select(this).style("opacity", 0.7).style("stroke-width", "3px");
      tooltip.style("opacity", 0);
    });

  // Draw dots
  g.selectAll(".slope-dot-min")
    .data(processedData)
    .join("circle")
    .attr("class", "slope-dot")
    .attr("cx", xPositions[0])
    .attr("cy", d => yScale(d.minAvg))
    .attr("r", 3)
    .attr("fill", d => colorScale(d.hospital))
    .attr("stroke", "#fff")
    .attr("stroke-width", 1);

  g.selectAll(".slope-dot-max")
    .data(processedData)
    .join("circle")
    .attr("class", "slope-dot")
    .attr("cx", xPositions[1])
    .attr("cy", d => yScale(d.maxAvg))
    .attr("r", 3)
    .attr("fill", d => colorScale(d.hospital))
    .attr("stroke", "#fff")
    .attr("stroke-width", 1);

  // Add labels
  g.append("text")
    .attr("x", xPositions[0])
    .attr("y", -10)
    .attr("text-anchor", "middle")
    .attr("fill", "#e2e8f0")
    .style("font-size", "11px")
    .text("Min Price");

  g.append("text")
    .attr("x", xPositions[1])
    .attr("y", -10)
    .attr("text-anchor", "middle")
    .attr("fill", "#e2e8f0")
    .style("font-size", "11px")
    .text("Max Price");

  // Add y-axis with better formatting
  const yAxisFormat = d => {
    if (d >= 1000000) return `$${(d/1000000).toFixed(1)}M`;
    if (d >= 1000) return `$${(d/1000).toFixed(0)}k`;
    return `$${d.toFixed(0)}`;
  };
  
  g.append("g")
    .attr("class", "axis")
    .call(d3.axisLeft(yScale).tickFormat(yAxisFormat));
}

/**
 * Update all visualizations with new data
 * @param {Array} hospitalList - List of hospitals
 * @param {Map} hitsById - Map of hospital IDs to price hits
 */
function updateVisualizations(hospitalList, hitsById) {
  // Prepare data
  const allHits = [];
  const hospitalData = hospitalList.map(h => {
    const hits = hitsById.get(h.id) || [];
    allHits.push(...hits);
    return { ...h, hits };
  });

  // Update charts
  createDistributionChart(allHits);
  createSlopegraph(hospitalData);
}

// ========================================
// HOSPITAL RENDERING AND DISPLAY
// ========================================

// Store current data for visualization updates
let currentHospitalList = [];
let currentHitsById = new Map();

/**
 * Toggle function for expanding/collapsing hospital price display
 * Made global so it can be called from HTML onclick attributes
 * @param {string} hospitalId - ID of the hospital element to toggle
 */
window.toggleHospitalPrices = (hospitalId) => {
  const pricesDiv = document.getElementById(hospitalId);
  const toggleIndicator = document.getElementById(`toggle-${hospitalId}`);
  
  if (pricesDiv && toggleIndicator) {
    const isExpanded = pricesDiv.classList.contains('expanded');
    
    if (isExpanded) {
      pricesDiv.classList.remove('expanded');
      toggleIndicator.classList.remove('expanded');
      toggleIndicator.textContent = '▶';
    } else {
      pricesDiv.classList.add('expanded');
      toggleIndicator.classList.add('expanded');
      toggleIndicator.textContent = '▼';
    }
  }
};

/**
 * Render hospital list in sidebar with price data
 * @param {Array} hlist - List of hospitals to display
 * @param {Map} hitsById - Map of hospital IDs to price matches
 */
function renderHospitals(hlist, hitsById){
  $list.innerHTML = "";
  $listTitle.textContent = `Hospitals (${hlist.length})`;
  
  // Sort hospitals by distance if ZIP code is available
  const enteredZip = $zip.value.trim();
  let sortedHospitals = [...hlist]; // Create a copy to avoid mutating original array
  
  if (enteredZip && ZIP.has(enteredZip)) {
    const zipCoords = ZIP.get(enteredZip);
    if (zipCoords && zipCoords.length === 2) {
      const [zipLat, zipLon] = zipCoords;
      if (isFinite(zipLat) && isFinite(zipLon)) {
        sortedHospitals.sort((a, b) => {
          // Calculate distance for hospital a
          let distanceA = Infinity;
          if (isFinite(a.lat) && isFinite(a.lon)) {
            distanceA = gcMiles([zipLon, zipLat], [a.lon, a.lat]);
          }
          
          // Calculate distance for hospital b
          let distanceB = Infinity;
          if (isFinite(b.lat) && isFinite(b.lon)) {
            distanceB = gcMiles([zipLon, zipLat], [b.lon, b.lat]);
          }
          
          return distanceA - distanceB; // Sort closest first
        });
      }
    }
  }
  
  // Update hospital markers on map
  const pts = hospLayer.selectAll("circle.marker-hosp").data(hlist, d=>d.id);
  pts.join(
    en => en.append("circle").attr("class","marker-hosp").attr("r",3.5)
              .attr("cx", d => projection(d.ll)?.[0] ?? -9999)
              .attr("cy", d => projection(d.ll)?.[1] ?? -9999),
    up => up.attr("cx", d => projection(d.ll)?.[0] ?? -9999)
            .attr("cy", d => projection(d.ll)?.[1] ?? -9999),
    ex => ex.remove()
  );

  // Render hospital cards in sidebar
  for(const h of sortedHospitals){
    const div = document.createElement("div"); div.className = "card";
    const hits = hitsById.get(h.id) || [];
    const hospitalId = `hospital-${h.id}`;
    
    // Calculate distance from entered ZIP code if available
    let distanceText = "";
    const enteredZip = $zip.value.trim();
    if (enteredZip && ZIP.has(enteredZip) && isFinite(h.lat) && isFinite(h.lon)) {
      const zipCoords = ZIP.get(enteredZip);
      if (zipCoords && zipCoords.length === 2) {
        const [zipLat, zipLon] = zipCoords;
        if (isFinite(zipLat) && isFinite(zipLon)) {
          const distance = gcMiles([zipLon, zipLat], [h.lon, h.lat]);
          distanceText = `${distance.toFixed(0)} mi`;
        }
      }
    }
    
    div.innerHTML = `
      <div class="hospital-header" onclick="toggleHospitalPrices('${hospitalId}')">
        <div>
          <strong>${h.name}</strong> 
          <span class="badge">${h.state ?? ""}</span>
          <span class="badge">${distanceText}</span>
          <span class="toggle-indicator" id="toggle-${hospitalId}">▶</span>
        </div>
        <div class="small">${h.address ?? ""}, ${h.city ?? ""}, ${h.zip ?? ""}</div>
        ${hits.length ? `<div style="margin-top:.4rem"><strong>${hits.length}</strong> match${hits.length>1?"es":""} found - click to view</div>` : `<div class="small" style="margin-top:.4rem">No matches in file</div>`}
      </div>
      ${hits.length ? `
        <div class="hospital-prices" id="${hospitalId}">
          ${hits.slice(0,hits.length).map(r => `
            <div class="price-item">
              ${r.payer_name || r.plan_name ? `
                <div class="payer-info">
                  ${r.payer_name ? r.payer_name : ""}${r.payer_name && r.plan_name ? " - " : ""}${r.plan_name ? r.plan_name : ""}
                </div>
              ` : ""}
              <div style="margin-bottom:.4rem"><code>${getCodeField(r)}</code> — ${r.description ?? ""}</div>
              ${generatePriceTable(r)}
            </div>
          `).join("")}
        </div>
      ` : ""}
    `;
    
    // Add click handler for map zoom (only on hospital name area, not the toggle)
    const hospitalNameArea = div.querySelector('.hospital-header > div:first-child strong');
    if (hospitalNameArea) {
      hospitalNameArea.style.cursor = 'pointer';
      hospitalNameArea.onclick = (e) => {
        e.stopPropagation(); // Prevent triggering the toggle
        const p = projection(h.ll); if(!p) return;
        svg.transition().duration(600)
          .call(zoom.transform, d3.zoomIdentity.translate(WIDTH/2 - p[0]*6, HEIGHT/2 - p[1]*6).scale(6));
      };
    }
    
    $list.appendChild(div);
  }
  
  // Store current data and update visualizations
  currentHospitalList = hlist;
  currentHitsById = hitsById;
  updateVisualizations(hlist, hitsById);
}

// ========================================
// MAIN SEARCH FUNCTIONALITY
// ========================================

// Global data storage
let ZIP = new Map();
let hospitals = [];

/**
 * Main search function - finds hospitals and queries their price data
 * Handles various search radius modes and updates UI accordingly
 */
async function go(){
  const rawZip = ($zip.value||"").trim();
  const zip = rawZip.padStart(5,'0').slice(-5);
  const miles = +$radius.value;
  const svcName = $service.value;
  const q = ($q.value||"").trim();
  const selectedPayer = $payer.value || null;
  
  // Get the search pattern - either from service or custom query
  let searchPattern = '';
  const configMap = currentConfigType === 'service' ? services : revenueCodes;
  
  if (svcName && svcName !== 'custom' && configMap.has(svcName)) {
    const svcRegex = configMap.get(svcName);
    searchPattern = svcRegex.source; // Get the regex pattern string
  } else if (svcName === 'custom' && q) {
    searchPattern = q;
  }

  if(!ZIP.has(zip)){ setStatus(`ZIP ${zip} not found.`); return; }
  if(!hospitals.length){ setStatus("No hospitals index loaded."); return; }

  const [lat,lon] = ZIP.get(zip); const center = [lon, lat];
  
  let nearby;
  if (miles >= 500) {
    // 500+ mode: show all hospitals, no circle, no zoom
    circlePath.style("display", "none");
    nearby = hospitals.filter(h => isFinite(h.lon) && isFinite(h.lat));
    const p = projection(center); if(p) zipMarker.attr("cx", p[0]).attr("cy", p[1]).style("display", null);
    setStatus(`Showing all ${nearby.length} hospitals. Loading payers...`);
  } else {
    // Normal radius mode
    const circle = d3.geoCircle().center(center).radius(miles2deg(miles))();
    circlePath.datum(circle).attr("d", path).style("display", null);
    const p = projection(center); if(p) zipMarker.attr("cx", p[0]).attr("cy", p[1]).style("display", null);
    zoomTo(circle);
    nearby = hospitals.filter(h => isFinite(h.lon) && isFinite(h.lat) && gcMiles(center, h.ll) <= miles);
    setStatus(`Found ${nearby.length} hospitals within ${miles} mi. Loading payers...`);
  }

  // Load unique payers from hospitals in radius
  try {
    const uniquePayers = await getUniquePayers(nearby);
    populatePayerDropdown(uniquePayers);
    const searchDesc = svcName || q;
    const statusMsg = miles >= 500 
      ? `Showing all ${nearby.length} hospitals. ${searchDesc ? "Querying prices..." : "(select a service or enter a procedure to search prices)"}`
      : `Found ${nearby.length} hospitals within ${miles} mi. ${searchDesc ? "Querying prices..." : "(select a service or enter a procedure to search prices)"}`;
    setStatus(statusMsg);
  } catch (e) {
    console.warn("Failed to load payers:", e);
    const searchDesc = svcName || q;
    const statusMsg = miles >= 500 
      ? `Showing all ${nearby.length} hospitals. ${searchDesc ? "Querying prices..." : "(select a service or enter a procedure to search prices)"}`
      : `Found ${nearby.length} hospitals within ${miles} mi. ${searchDesc ? "Querying prices..." : "(select a service or enter a procedure to search prices)"}`;
    setStatus(statusMsg);
  }

  // Query price data from hospital JSON files in parallel
  const hitsById = new Map();
  const pool = 4; let i = 0;
  async function worker(){
    while(i < nearby.length){
      const h = nearby[i++];
      const hits = (ENABLE_PRICES && searchPattern && h.json_path) ? await queryHospitalJSON(h.json_path, searchPattern, selectedPayer) : [];
      hitsById.set(h.id, hits);
    }
  }
  await Promise.all(Array.from({length: pool}, worker));
  
  // Render results
  renderHospitals(nearby, hitsById);
  const searchDesc = svcName || q;
  const doneMsg = miles >= 500 
    ? `Done. All ${nearby.length} hospitals searched${searchDesc ? ` for "${searchDesc}"` : ""}.`
    : `Done. ${nearby.length} hospitals searched${searchDesc ? ` for "${searchDesc}"` : ""}.`;
  setStatus(doneMsg);
}

// ========================================
// EVENT LISTENERS AND INITIALIZATION
// ========================================

/**
 * Initialize the application
 * Loads all necessary data and sets up event listeners
 */
async function initializeApp() {
  // Load basemap first
  await initializeBasemap();
  
  // Load data files
  ZIP = await loadZipData();
  hospitals = await loadHospitalData();
  const serviceMap = await loadServiceConfig();
  const rcMap = await loadRevenueCodeConfig();
  const medicareRates = await loadMedicareRates();
  
  // Store loaded data in global maps
  serviceMap.forEach((regex, name) => services.set(name, regex));
  rcMap.forEach((regex, name) => revenueCodes.set(name, regex));
  medicareRates.forEach((rate, code) => cmsRate.set(code, rate));
  
  // Initialize dropdown with service configuration
  populateServiceDropdown('service');
  
  setStatus("Ready to search JSON price files.");
}

// Set up event listeners
$configType.addEventListener('change', handleConfigTypeChange);
$service.addEventListener('change', handleServiceChange);
$go.addEventListener("click", go);
$zip.addEventListener("keydown", e => { if(e.key==="Enter") go(); });
$radius.addEventListener("change", go);
$payer.addEventListener("change", go);
$unit.addEventListener("change", () => {
  go(); // This will refresh both tables and visualizations
});

// Initialize the application when the DOM is loaded
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeApp);
} else {
  initializeApp();
}