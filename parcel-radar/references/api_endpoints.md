# King County GIS API Endpoints

## GIS Services Root

```
https://gismaps.kingcounty.gov/arcgis/rest/services/
```

## Address Services

| Service | Type | URL |
|---------|------|-----|
| Address Points Locator | GeocodeServer | `.../Address/Address_Points_locator/GeocodeServer` |
| Composite Locator | GeocodeServer | `.../Address/Composite_locator/GeocodeServer` |
| Four County Locator | GeocodeServer | `.../Address/FourCounty_locator/GeocodeServer` |
| Address Points Map | MapServer | `.../Address/KingCo_AddressPoints/MapServer` |
| **Parcel Address Locator** | GeocodeServer | `.../Address/KingCo_ParcelAddress_locator/GeocodeServer` |
| Zipcode Map | MapServer | `.../Address/KingCo_zipcode/MapServer` |
| TNET Streets | GeocodeServer | `.../Address/TNET_Streets/GeocodeServer` |

All URLs are relative to `https://gismaps.kingcounty.gov/arcgis/rest/services/`

## Parcel Map Service

```
https://gismaps.kingcounty.gov/arcgis/rest/services/Property/KingCo_Parcels/MapServer/0
```

Fields: `OBJECTID`, `MAJOR`, `MINOR`, `PIN`, `Shape`

Query by PIN:
```
.../MapServer/0/query?where=PIN='{PIN}'&outFields=*&f=json
```

## Geocode Query Format

```
.../GeocodeServer/findAddressCandidates?SingleLine={ADDRESS}&outFields=*&f=json
```

Response fields of interest:
- `attributes.PIN` - Parcel identification number (10 digits)
- `attributes.City` - City name
- `attributes.Subregion` - County
- `attributes.Postal` - ZIP code
- `attributes.PostalExt` - ZIP+4
- `location.x`, `location.y` - Coordinates (State Plane, WKID 2926)
- `score` - Match confidence (100 = exact)

## Assessor eRealProperty

```
https://blue.kingcounty.com/Assessor/eRealProperty/Dashboard.aspx?ParcelNbr={PIN}
```

Returns HTML page with: owner, assessed values, building details, tax info, historical values.
