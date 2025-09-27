# CLEAR
Chargemaster Location-based Exploration for Affordability &amp; Reform

NOTE: Some hospitals are not fully transparant about pricing policy, they only provide estimates and insurance names for APC codes (bundled HCPCS codes), so a cross-walk using `Addendum B` published by CMS needs to be used in order to map codes to prices. Even then this is a poor method that doesn't grab all the matches needed (causing dupe issues needed to be reviewed by hand). 

## About This Tool
The Hospital Price Finder helps you discover and compare healthcare procedure costs across hospitals within a specified radius of any ZIP code. Search by procedure codes (CPT, HCPCS) or custom patterns to find pricing transparency data from hospital charge masters.

## How to Use
- Select a predefined service or enter a custom procedure pattern (regex supported)
- Enter a ZIP code and choose your search radius
- Optionally filter by insurance payer or view prices as ratios to Medicare rates
- Click search to see hospitals on the map and pricing data in the sidebar
- Scroll down to analyze price distributions and hospital comparisons
- Use the reset zoom button to return to the full map view

Hospitals that have been added to this 'web-app' are stored in a `.csv` file for quick look up and ease of access**. This points to the loc of it's Charge Master `.json` file which is then queried for the specific procedure. Hospitals are gathered from the CSV list based on a radius look-up provided by the user. If a hospital in the radius does not offer the service, it will not display the price point compared to others in the radius. 

Currently limited to 500 procedures due to file size limits and me not wanting to set up a server/database for this. Parquet only works server side so i can't do iterative testing before publishing to pages, and pages deployments can take a while. Will consider moving to parquet system after front-end is stable and working as envisioned.

>**Note: The `hospitals.csv` will need to be updated with the hospital name, city, zip, and address before running code to add a new hospital. The notebook will autopopulate the .json path structure, unique filename, and >latitude/longitude, but these other elements NEED TO BE PRESENT FIRST TO WORK. 

## List of Hospitals

These are the hospital's which data has been gathered and processed for thus far:

| State    | Hospital Name                     | Zipcode     | Date                 | File Size    | Link                                                            |
|----------|--------------------------------|-------------|-------------------|-------------|------------------------------------------------|
| NC        | Duke University Hospital     |     27710    |      09/2025      |   3.32 GB   |    [Link](https://www.dukehealth.org/paying-for-care/what-duke-charges-services) |
| NC        | AdventHealth (Hendersonville)   |     28792   |   09/2025    |      1.48 GB           |                                                                 |
| SC        | MUSC Health-University Medical Center (Charleston) |   29425   | 09/2025 | 11.8 MB |  [Link](https://muschealth.org/patients-visitors/billing/price-transparency) |

## Data Processing

CSV files are too large to store on github, thus they are downloaded locally, converted to the necessary format, then uploaded. If you want to perform conversions yourself you will need to find the specific hospital chargemaster and document in the notebook accordingly.

Not all Charge Masters (CM) are formatted the same, as such, to keep the notebook from growing too large, custom python scripts will be made for unique CM's. This matters beccause some hospitals are regional or statewide 'chains' but can vary prices between locations. For example, 

**AdventHealth**
- AdventHealth Orlando
- AdventHealth Tampa
- AdventHealth Hendersonville

all are AdventHealth hospitals, but their prices and available procedures vary per location. However, the same script to clean and process their CM's works because the file structure doesn't change from loc to loc. Normally CM structure only changes from hospital to hospital (brand-wise), but I haven't looked at the majority of US hospitals so this statement might need to be amended. 

Think of the `CLEAR.ipynb` notebook as more of a "**Controller**" for the cleaning, while the cleaning process is performed by imported functions found in scripts. Subsections from here on are labeled by State, be sure to check which Hospitals are in each subsection before uploading data. 


## Outside Sources Used

- zip_centroids.csv courtesy of SimpleMaps data https://simplemaps.com/data/us-zips.
- CMS.gov data for top 200 HCPCS and CPT codes billed for 2024 & top 100 lab codes. [Link](https://www.cms.gov/data-research/statistics-trends-and-reports/medicare-fee-for-service-parts-a-b/medicare-utilization-part-b)
