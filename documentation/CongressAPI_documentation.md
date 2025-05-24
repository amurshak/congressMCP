# **Congress.gov Bill API Documentation**

## **Overview**

The Congress.gov Bill API provides structured access to legislative bill data, including metadata, actions, amendments, sponsors, summaries, subjects, text versions, and more.

Base URL: `https://api.congress.gov/v3/bill`

All endpoints require an API key provided via `?api_key=[INSERT_KEY]`.

---

## **Endpoints**

### **GET `/bill`**

**Description**: Returns a list of bills sorted by date of latest action.

**Example Request**:

GET /bill?api\_key=\[INSERT\_KEY\]

**Example Response**:

{  
  "bills": \[  
    {  
      "congress": 117,  
      "latestAction": {  
        "actionDate": "2022-04-06",  
        "text": "Became Public Law No: 117-108."  
      },  
      "number": "3076",  
      "originChamber": "House",  
      "originChamberCode": "H",  
      "title": "Postal Service Reform Act of 2022",  
      "type": "HR",  
      "updateDate": "2022-09-29",  
      "updateDateIncludingText": "2022-09-29T03:27:05Z",  
      "url": "https://api.congress.gov/v3/bill/117/hr/3076?format=json"  
    },  
    {  
      "congress": 117,  
      "latestAction": {  
        "actionDate": "2022-04-06",  
        "text": "Read twice. Placed on Senate Legislative Calendar under General Orders. Calendar No. 343."  
      },  
      "number": "3599",  
      "originChamber": "House",  
      "originChamberCode": "H",  
      "title": "Federal Rotational Cyber Workforce Program Act of 2021",  
      "type": "HR",  
      "updateDate": "2022-09-29",  
      "updateDateIncludingText": "2022-09-29",  
      "url": "https://api.congress.gov/v3/bill/117/hr/3599?format=json"  
    }  
  \]  
}

**Query Parameters**:

* `format` (string): xml or json  
* `offset` (integer)  
* `limit` (integer, max 250\)  
* `fromDateTime` (string): YYYY-MM-DDT00:00:00Z  
* `toDateTime` (string): YYYY-MM-DDT00:00:00Z  
* `sort` (string): updateDate+asc or updateDate+desc

---

### **GET `/bill/{congress}`**

**Description**: Returns bills from a specified Congress.

**Example Request**:

GET /bill/117?api\_key=\[INSERT\_KEY\]

**Example Response**:

{  
  "bills": \[ ... \]  
}

**Path Parameter**:

* `congress` (integer) – e.g. 117

**Query Parameters**: Same as above

---

### **GET `/bill/{congress}/{billType}`**

**Description**: Returns bills filtered by Congress and bill type.

**Example Request**:

GET /bill/117/hr?api\_key=\[INSERT\_KEY\]

**Example Response**:

{  
  "bills": \[ ... \]  
}

**Path Parameters**:

* `congress` (integer)  
* `billType` (string): hr, s, hjres, sjres, hconres, sconres, hres, sres

**Query Parameters**: Same as above

---

### **GET `/bill/{congress}/{billType}/{billNumber}`**

**Description**: Returns detailed data for a specific bill.

**Example Request**:

GET /bill/117/hr/3076?api\_key=\[INSERT\_KEY\]

**Example Response**:

{  
  "bill": {  
    "number": "3076",  
    "title": "Postal Service Reform Act of 2022",  
    "actions": { "count": 74, "url": "..." },  
    "amendments": { "count": 48, "url": "..." },  
    "cosponsors": { "count": 102, "url": "..." },  
    "summaries": { "count": 5, "url": "..." },  
    "textVersions": { "count": 8, "url": "..." },  
    "titles": { "count": 14, "url": "..." }  
  }  
}  
---

### **GET `/bill/{congress}/{billType}/{billNumber}/actions`**

**Example Response**:

{  
  "actions": \[  
    {  
      "actionCode": "36000",  
      "actionDate": "2022-04-06",  
      "text": "Became Public Law No: 117-108.",  
      "type": "BecameLaw"  
    }  
  \]  
}

### **GET `/bill/{congress}/{billType}/{billNumber}/amendments`**

**Example Response**:

{  
  "amendments": \[  
    {  
      "number": "173",  
      "description": "Amendment clarifies roles and responsibilities...",  
      "latestAction": { "actionDate": "2022-02-08", "text": "Agreed to by voice vote." }  
    }  
  \]  
}

### **GET `/bill/{congress}/{billType}/{billNumber}/committees`**

**Example Response**:

{  
  "committees": \[  
    {  
      "name": "Oversight and Reform Committee",  
      "chamber": "House",  
      "activities": \[  
        { "date": "2021-05-11T18:05:40Z", "name": "Referred to" }  
      \]  
    }  
  \]  
}

### **GET `/bill/{congress}/{billType}/{billNumber}/cosponsors`**

**Example Response**:

{  
  "cosponsors": \[  
    {  
      "fullName": "Rep. Connolly, Gerald E. \[D-VA-11\]",  
      "sponsorshipDate": "2021-05-11"  
    }  
  \]  
}

### **GET `/bill/{congress}/{billType}/{billNumber}/relatedbills`**

**Example Response**:

{  
  "relatedBills": \[  
    {  
      "number": 1720,  
      "title": "Postal Service Reform Act of 2021",  
      "relationshipDetails": \[ { "type": "Related bill" } \]  
    }  
  \]  
}

### **GET `/bill/{congress}/{billType}/{billNumber}/subjects`**

**Example Response**:

{  
  "subjects": {  
    "legislativeSubjects": \[  
      { "name": "Congressional oversight" }  
    \],  
    "policyArea": { "name": "Government Operations and Politics" }  
  }  
}

### **GET `/bill/{congress}/{billType}/{billNumber}/summaries`**

**Example Response**:

{  
  "summaries": \[  
    {  
      "actionDate": "2022-03-08",  
      "text": "This bill addresses the finances and operations of the USPS."  
    }  
  \]  
}

### **GET `/bill/{congress}/{billType}/{billNumber}/text`**

**Example Response**:

{  
  "textVersions": \[  
    {  
      "type": "Enrolled Bill",  
      "formats": \[  
        { "type": "PDF", "url": "https://.../BILLS-117hr3076enr.pdf" }  
      \]  
    }  
  \]  
}

### **GET `/bill/{congress}/{billType}/{billNumber}/titles`**

**Example Response**:

{  
  "titles": \[  
    {  
      "title": "Postal Service Reform Act of 2022",  
      "titleType": "Display Title"  
    }  
  \]  
}  
---

# **Congress.gov Amendment API Documentation**

## **Overview**

The Congress.gov Amendment API provides structured access to legislative amendment data, including metadata, actions, cosponsors, and related amendments.

Base URL: `https://api.congress.gov/v3/amendment`

All endpoints require an API key provided via `?api_key=[INSERT_KEY]`.

---

## **Endpoints**

### **GET `/amendment`**

**Description**: Returns a list of amendments sorted by date of latest action.

**Example Request**:

GET /amendment?api\_key=\[INSERT\_KEY\]

**Example Response**:

```json
{
    "amendments": [
        {
           "congress": 117,
           "latestAction": {
                "actionDate": "2021-08-08",
                "text": "Amendment SA 2137 agreed to in Senate by Yea-Nay Vote. 69 - 28. Record Vote Number: 312."
            },
            "number": "2137",
            "purpose": "In the nature of a substitute.",
            "type": "SAMDT",
            "url": "http://api.congress.gov/v3/amendment/117/samdt/2137?format=json"
        },
        {
            "congress": 117,
            "latestAction": {
                "actionDate": "2021-08-08",
                "text": "Amendment SA 2131 agreed to in Senate by Voice Vote. "
            },
            "number": "2131",
            "purpose": "To strike a definition.",
            "type": "SAMDT",
            "updateDate": "2022-02-25T17:34:49Z",
            "url": "https://api.congress.gov/v3/amendment/117/samdt/2131?format=json"
        }
    ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| format | The data format. Value can be xml or json. |
| offset | The starting record returned. 0 is the first record. |
| limit | The number of records returned. The maximum limit is 250. |
| fromDateTime | The starting timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |
| toDateTime | The ending timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |

### **GET `/amendment/{congress}`**

**Description**: Returns a list of amendments filtered by the specified congress, sorted by date of latest action.

**Example Request**:

GET /amendment/117?api\_key=\[INSERT\_KEY\]

**Example Response**:

```json
{
    "amendments": [
        {
           "congress": 117,
           "latestAction": {
                "actionDate": "2021-08-08",
                "text": "Amendment SA 2137 agreed to in Senate by Yea-Nay Vote. 69 - 28. Record Vote Number: 312."
            },
            "number": "2137",
            "purpose": "In the nature of a substitute.",
            "type": "SAMDT",
            "url": "http://api.congress.gov/v3/amendment/117/samdt/2137?format=json"
        },
        {
            "congress": 117,
            "latestAction": {
                "actionDate": "2021-08-08",
                "text": "Amendment SA 2131 agreed to in Senate by Voice Vote. "
            },
            "number": "2131",
            "purpose": "To strike a definition.",
            "type": "SAMDT",
            "updateDate": "2022-02-25T17:34:49Z",
            "url": "https://api.congress.gov/v3/amendment/117/samdt/2131?format=json"
        }
    ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| congress * | The congress number. For example, the value can be 117. |
| format | The data format. Value can be xml or json. |
| offset | The starting record returned. 0 is the first record. |
| limit | The number of records returned. The maximum limit is 250. |
| fromDateTime | The starting timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |
| toDateTime | The ending timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |

### **GET `/amendment/{congress}/{amendmentType}`**

**Description**: Returns a list of amendments filtered by the specified congress and amendment type, sorted by date of latest action.

**Example Request**:

GET /amendment/117/samdt?api\_key=\[INSERT\_KEY\]

**Example Response**:

```json
{
    "amendments": [
        {
           "congress": 117,
           "latestAction": {
                "actionDate": "2021-08-08",
                "text": "Amendment SA 2137 agreed to in Senate by Yea-Nay Vote. 69 - 28. Record Vote Number: 312."
            },
            "number": "2137",
            "purpose": "In the nature of a substitute.",
            "type": "SAMDT",
            "url": "http://api.congress.gov/v3/amendment/117/samdt/2137?format=json"
        },
        {
            "congress": 117,
            "latestAction": {
                "actionDate": "2021-08-08",
                "text": "Amendment SA 2131 agreed to in Senate by Voice Vote. "
            },
            "number": "2131",
            "purpose": "To strike a definition.",
            "type": "SAMDT",
            "updateDate": "2022-02-25T17:34:49Z",
            "url": "https://api.congress.gov/v3/amendment/117/samdt/2131?format=json"
        }
    ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| congress * | The congress number. For example, the value can be 117. |
| amendmentType * | The type of amendment. Value can be hamdt, samdt, or suamdt. |
| format | The data format. Value can be xml or json. |
| offset | The starting record returned. 0 is the first record. |
| limit | The number of records returned. The maximum limit is 250. |
| fromDateTime | The starting timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |
| toDateTime | The ending timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |

### **GET `/amendment/{congress}/{amendmentType}/{amendmentNumber}`**

**Description**: Returns detailed information for a specified amendment.

**Example Request**:

GET /amendment/117/samdt/2137?api\_key=\[INSERT\_KEY\]

**Example Response**:

```json
{
    "amendment": {
        "actions": {
            "count": 19,
            "url": "https://api.congress.gov/v3/amendment/117/samdt/2137/actions?format=json"
        },
        "amendedBill": {
            "congress": 117,
            "number": "3684",
            "originChamber": "House",
            "originChamberCode": "H",
            "title": "Infrastructure Investment and Jobs Act",
            "type": "HR",
            "url": "https://api.congress.gov/v3/bill/117/hr/3684?format=json"
        },
        "amendmentsToAmendment": {
             "count": 507,
             "url": "https://api.congress.gov/v3/amendment/117/samdt/2137/amendments?format=json"
        },
        "chamber": "Senate",
        "congress": 117,
        "cosponsors": {
            "count": 9,
            "countIncludingWithdrawnCosponsors": 9,
            "url": "https://api.congress.gov/v3/amendment/117/samdt/2137/cosponsors?format=json"
        },
        "latestAction": {
            "actionDate": "2021-08-08",
            "text": "Amendment SA 2137 agreed to in Senate by Yea-Nay Vote. 69 - 28. Record Vote Number: 312."
        },
        "number": "2137",
        "proposedDate": "2021-08-01T04:00:00Z",
        "purpose": "In the nature of a substitute.",
        "sponsors": [
            {
                "bioguideId": "S001191",
                "firstName": "Kyrsten",
                "fullName": "Sen. Sinema, Kyrsten [D-AZ]",
                "lastName": "Sinema",
                "url": "https://api.congress.gov/v3/member/S001191?format=json"
            }
        ],
        "submittedDate": "2021-08-01T04:00:00Z",
        "type": "SAMDT",
        "updateDate": "2022-02-08T17:27:59Z"
    }
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| congress * | The congress number. For example, the value can be 117. |
| amendmentType * | The type of amendment. Value can be hamdt, samdt, or suamdt. |
| amendmentNumber * | The amendment's assigned number. For example, the value can be 2137. |
| format | The data format. Value can be xml or json. |

### **GET `/amendment/{congress}/{amendmentType}/{amendmentNumber}/actions`**

**Description**: Returns the list of actions on a specified amendment.

**Example Request**:

GET /amendment/117/samdt/2137/actions?api\_key=\[INSERT\_KEY\]

**Example Response**:

```json
{
    "actions": [
        {
           "actionDate": "2021-08-08",
           "recordedVotes": [
             {
               "chamber": "Senate",
               "congress": 117,
               "date": "2021-08-09T00:45:48Z",
               "rollNumber": 312,
               "sessionNumber": 1,
               "url": "https://www.senate.gov/legislative/LIS/roll_call_votes/vote1171/vote_117_1_00312.xml"
             }
           ],
           "sourceSystem": {
             "code": 0,
             "name": "Senate"
           },
           "text": "Amendment SA 2137 agreed to in Senate by Yea-Nay Vote. 69 - 28. Record Vote Number: 312.",
           "type": "Floor"
        },
        {
            "actionDate": "2021-08-08",
            "recordedVotes": [
                {
                    "chamber": "Senate",
                    "congress": 117,
                    "date": "2021-08-09T00:37:19Z",
                    "rollNumber": 311,
                    "sessionNumber": 1,
                    "url": "https://www.senate.gov/legislative/LIS/roll_call_votes/vote1171/vote_117_1_00311.xml"
                }
            ],
            "sourceSystem": {
                "code": 0,
                "name": "Senate"
            },
            "text": "Motion to waive all applicable budgetary discipline with respect to amendment SA 2137 agreed to in Senate by Yea-Nay Vote. 64 - 33. Record Vote Number: 311. ",
            "type": "Floor"
        }
    ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| congress * | The congress number. For example, the value can be 117. |
| amendmentType * | The type of amendment. Value can be hamdt, samdt, or suamdt. |
| amendmentNumber * | The amendment's assigned number. For example, the value can be 2137. |
| format | The data format. Value can be xml or json. |
| offset | The starting record returned. 0 is the first record. |
| limit | The number of records returned. The maximum limit is 250. |

### **GET `/amendment/{congress}/{amendmentType}/{amendmentNumber}/cosponsors`**

**Description**: Returns the list of cosponsors on a specified amendment.

**Example Request**:

GET /amendment/117/samdt/2137/cosponsors?api\_key=\[INSERT\_KEY\]

**Example Response**:

```json
{
    "cosponsors": [
        {
            "bioguideId": "P000449",
            "firstName": "Rob",
            "fullName": "Sen. Portman, Rob [R-OH]",
            "isOriginalCosponsor": true,
            "lastName": "Portman",
            "party": "R",
            "sponsorshipDate": "2021-08-01",
            "url": "https://api.congress.gov/v3/member/P000449?format=json"
        },
        {
            "bioguideId": "M001183",
            "firstName": "Joseph",
            "fullName": "Sen. Manchin, Joe, III [D-WV]",
            "isOriginalCosponsor": true,
            "lastName": "Manchin",
            "party": "D",
            "sponsorshipDate": "2021-08-01",
            "state": "WV",
            "url": "https://api.congress.gov/v3/member/M001183?format=json"
        }
    ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| congress * | The congress number. For example, the value can be 117. |
| amendmentType * | The type of amendment. Value can be hamdt, samdt, or suamdt. |
| amendmentNumber * | The amendment's assigned number. For example, the value can be 2137. |
| format | The data format. Value can be xml or json. |
| offset | The starting record returned. 0 is the first record. |
| limit | The number of records returned. The maximum limit is 250. |

### **GET `/amendment/{congress}/{amendmentType}/{amendmentNumber}/amendments`**

**Description**: Returns the list of amendments to a specified amendment.

**Example Request**:

GET /amendment/117/samdt/2137/amendments?api\_key=\[INSERT\_KEY\]

**Example Response**:

```json
{
    "amendments": [
        {
            "congress": 117,
            "latestAction": {
                "date": "2021-08-04",
                "text": "Amendment SA 2548 agreed to in Senate by Voice Vote."
            },
            "number": "2548",
            "purpose": "To require the Secretary of Agriculture to establish a Joint Chiefs Landscape Restoration Partnership program.",
            "type": "SAMDT",
            "url": "https://api.congress.gov/v3/amendment/117/samdt/2548?format=json"
        },
        {
            "congress": 117,
            "number": "2547",
            "type": "SAMDT",
            "updateDate": "2022-02-25T17:34:50Z",
            "url": "https://api.congress.gov/v3/amendment/117/samdt/2547?format=json"
        }
    ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| congress * | The congress number. For example, the value can be 117. |
| amendmentType * | The type of amendment. Value can be hamdt, samdt, or suamdt. |
| amendmentNumber * | The amendment's assigned number. For example, the value can be 2137. |
| format | The data format. Value can be xml or json. |
| offset | The starting record returned. 0 is the first record. |
| limit | The number of records returned. The maximum limit is 250. |

### **GET `/amendment/{congress}/{amendmentType}/{amendmentNumber}/text`**

**Description**: Returns the list of text versions for a specified amendment from the 117th Congress onwards.

**Example Request**:

GET /amendment/117/hamdt/287/text?api\_key=\[INSERT\_KEY\]

**Example Response**:

```json
{
    "textVersions": [
        {
            "date": "2022-07-14T06:20:29Z",
            "formats": [
                {
                    "type": "PDF",
                    "url":"https://www.congress.gov/117/crec/2022/07/13/168/115/CREC-2022-07-13-pt2-PgH6339-2.pdf"
                },
                {
                    "type": "Formatted XML",
                    "url": "https://www.congress.gov/117/crec/2022/07/13/168/115/modified/CREC-2022-07-13-pt2-PgH6339-2.htm"
                }
            ],
            "type": "Offered"
        }
    ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| congress * | The congress number. This is endpoint is for the 117th Congress and onwards. For example, the value can be 117. |
| amendmentType * | The type of amendment. Value can be hamdt or samdt. |
| amendmentNumber * | The bill's assigned number. For example, the value can be 287. |
| format | The data format. Value can be xml or json. |
| offset | The starting record returned. 0 is the first record. |
| limit | The number of records returned. The maximum limit is 250. |

---

## **Congress API**

### **GET `/congress`**

**Description**: Returns a list of congresses and congressional sessions.

**Example Request**:

```
https://api.congress.gov/v3/congress?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
  "congresses": [
    {
      "endYear": "2026",
      "name": "119th Congress",
      "number": 119,
      "sessions": [
        {
          "chamber": "Senate",
          "endDate": null,
          "number": 1,
          "startDate": "2025-01-03",
          "type": "R"
        },
        {
          "chamber": "House of Representatives",
          "endDate": null,
          "number": 1,
          "startDate": "2025-01-03",
          "type": "R"
        }
      ],
      "startYear": "2025",
      "updateDate": "2025-01-03T18:29:19Z",
      "url": "https://api.congress.gov/v3/congress/119?format=json"
    },
    {
      "endYear": "2024",
      "name": "118th Congress",
      "number": 118,
      "sessions": [
        {
          "chamber": "House of Representatives",
          "endDate": "2024-01-03",
          "number": 1,
          "startDate": "2023-01-03",
          "type": "R"
        },
        {
          "chamber": "Senate",
          "endDate": "2024-01-03",
          "number": 1,
          "startDate": "2023-01-03",
          "type": "R"
        },
        {
          "chamber": "Senate",
          "endDate": "2025-01-03",
          "number": 2,
          "startDate": "2024-01-03",
          "type": "R"
        },
        {
          "chamber": "House of Representatives",
          "endDate": "2025-01-03",
          "number": 2,
          "startDate": "2024-01-03",
          "type": "R"
        }
      ],
      "startYear": "2023",
      "updateDate": "2023-01-03T18:29:19Z",
      "url": "https://api.congress.gov/v3/congress/118?format=json"
    }
  ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| format | The data format. Value can be xml or json. |
| offset | The starting record returned. 0 is the first record. |
| limit | The number of records returned. The maximum limit is 250. |

### **GET `/congress/{congress}`**

**Description**: Returns detailed information about a specific Congress.

**Example Request**:

```
https://api.congress.gov/v3/congress/117?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
  "congress": {
    "endYear": "2022",
    "name": "117th Congress",
    "number": 117,
    "sessions": [
      {
        "chamber": "House of Representatives",
        "endDate": "2022-01-03",
        "number": 1,
        "startDate": "2021-01-03",
        "type": "R"
      },
      {
        "chamber": "Senate",
        "endDate": "2022-01-03",
        "number": 1,
        "startDate": "2021-01-03",
        "type": "R"
      },
      {
        "chamber": "House of Representatives",
        "endDate": "2023-01-03",
        "number": 2,
        "startDate": "2022-01-03",
        "type": "R"
      },
      {
        "chamber": "Senate",
        "endDate": "2023-01-03",
        "number": 2,
        "startDate": "2022-01-03",
        "type": "R"
      }
    ],
    "startYear": "2021",
    "updateDate": "2021-01-12T20:05:52Z",
    "url": "https://api.congress.gov/v3/congress/117?format=json"
  }
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| congress * | The congress number. For example, the value can be 117. |
| format | The data format. Value can be xml or json. |
| detailed | Whether to include detailed information. Value can be true or false. |

### **GET `/congress/current`**

**Description**: Returns detailed information about the current Congress.

**Example Request**:

```
https://api.congress.gov/v3/congress/current?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
  "congress": {
    "endYear": "2026",
    "name": "119th Congress",
    "number": 119,
    "sessions": [
      {
        "chamber": "Senate",
        "endDate": null,
        "number": 1,
        "startDate": "2025-01-03",
        "type": "R"
      },
      {
        "chamber": "House of Representatives",
        "endDate": null,
        "number": 1,
        "startDate": "2025-01-03",
        "type": "R"
      }
    ],
    "startYear": "2025",
    "updateDate": "2025-01-03T18:29:19Z",
    "url": "https://api.congress.gov/v3/congress/119?format=json"
  }
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| format | The data format. Value can be xml or json. |
| detailed | Whether to include detailed information. Value can be true or false. |

### **GET `/committee/{chamber}`**

**Description**: Returns a list of committees for a specific chamber.

**Example Request**:

```
https://api.congress.gov/v3/committee/house?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
  "committees": [
    {
      "name": "Agriculture",
      "systemCode": "hsag",
      "url": "https://api.congress.gov/v3/committee/house/hsag?format=json"
    },
    {
      "name": "Appropriations",
      "systemCode": "hsap",
      "url": "https://api.congress.gov/v3/committee/house/hsap?format=json"
    },
    {
      "name": "Armed Services",
      "systemCode": "hsas",
      "url": "https://api.congress.gov/v3/committee/house/hsas?format=json"
    }
  ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| chamber * | The chamber of Congress. Value must be "house" or "senate". |
| format | The data format. Value can be xml or json. |

### **GET `/committee/{chamber}/{committeeCode}/bills`**

**Description**: Returns a list of bills referred to a specific committee.

**Example Request**:

```
https://api.congress.gov/v3/committee/house/hsag/bills?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
  "bills": [
    {
      "congress": 117,
      "number": "4421",
      "title": "Agriculture Innovation Act of 2021",
      "type": "hr",
      "updateDate": "2022-07-19T03:41:41Z",
      "url": "https://api.congress.gov/v3/bill/117/hr/4421?format=json"
    },
    {
      "congress": 117,
      "number": "2936",
      "title": "Healthy Soil, Resilient Farmers Act of 2021",
      "type": "hr",
      "updateDate": "2022-05-01T03:41:41Z",
      "url": "https://api.congress.gov/v3/bill/117/hr/2936?format=json"
    }
  ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| chamber * | The chamber of Congress. Value must be "house" or "senate". |
| committeeCode * | The committee code. For example, the value can be "hsag" for House Agriculture Committee. |
| format | The data format. Value can be xml or json. |
| offset | The starting record returned. 0 is the first record. |
| limit | The number of records returned. The maximum limit is 250. |

---

## **MCP Tools for Congress API**

### **get_congress_info**

**Description**: Get information about a Congress.

**Parameters**:

| Name | Description | Required | Default |
|------|-------------|----------|--------|
| congress | Congress number (e.g., 117 for 117th Congress) | No | None |
| current | If True, get information about the current Congress | No | False |
| limit | Maximum number of congresses to return if no specific congress is requested | No | 10 |
| detailed | If True, include more detailed information about the Congress | No | False |
| format_type | Output format type ("markdown" or "table") for list of congresses | No | "markdown" |

**Example**:

```python
result = await get_congress_info(congress=117, detailed=True)
```

### **get_committee_bills**

**Description**: Get bills referred to a specific committee.

**Parameters**:

| Name | Description | Required | Default |
|------|-------------|----------|--------|
| chamber | The chamber of Congress ("house" or "senate") | Yes | N/A |
| committee_code | The committee code (e.g., "hsag", "ssap") | Yes | N/A |
| limit | Maximum number of bills to return | No | 10 |

**Example**:

```python
result = await get_committee_bills(chamber="house", committee_code="hsag", limit=20)
```

---

## **Summaries API**

### **GET `/summaries`**

**Description**: Returns a list of summaries sorted by date of last update.

**Example Request**:

```
https://api.congress.gov/v3/summaries?fromDateTime=2022-04-01T00:00:00Z&toDateTime=2022-04-03T00:00:00Z&sort=updateDate+asc&api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
     "summaries": [
        {
            "actionDate": "2021-02-04",
            "actionDesc": "Introduced in Senate",
            "bill": {
                "congress": 117,
                "number": "225",
                "originChamber": "Senate",
                "originChamberCode": "S",
                "title": "Competition and Antitrust Law Enforcement Reform Act of 2021",
                "type": "S",
                "updateDateIncludingText": "2022-09-29T03:41:41Z",
                "url": "https://api.congress.gov/v3/bill/117/s/225?format=json"
            },
            "currentChamber": "Senate",
            "currentChamberCode": "S",
            "lastSummaryUpdateDate": "2022-03-31T15:20:50Z",
            "text": " <p><strong>Competition and Antitrust Law Enforcement Reform Act of 2021 </strong></p> <p>This bill revises antitrust laws applicable to mergers and anticompetitive conduct. </p> <p>Specifically, the bill applies a stricter standard for permissible mergers by prohibiting mergers that (1) create an appreciable risk of materially lessening competition, or (2) unfairly lower the prices of goods or wages because of a lack of competition among buyers or employers (i.e., a monopsony). Under current law, mergers that substantially lessen competition are prohibited. </p> <p>Additionally, for some large mergers or mergers that concentrate markets beyond a certain threshold, the bill shifts the burden of proof to the merging parties to prove that the merger does not violate the law. </p> <p>The bill also prohibits exclusionary conduct that presents an appreciable risk of harming competition. </p> <p>The bill also establishes monetary penalties for violations, requires annual reporting for certain mergers and acquisitions, establishes within the Federal Trade Commission (FTC) the Office of the Competition Advocate, and sets forth whistleblower protections. </p> <p>The Government Accountability Office must report on (1) the success of merger remedies required by the Department of Justice or the FTC in recent consent decrees; and (2) the impact of mergers and acquisitions on wages, employment, innovation, and new business formation.</p>",
            "updateDate": "2022-04-01T03:31:17Z",
            "versionCode": "00"
        },
        {
            "actionDate": "2022-03-24",
            "actionDesc": "Introduced in Senate",
            "bill": {
                "congress": 117,
                "number": "3914",
                "originChamber": "Senate",
                "originChamberCode": "S",
                "title": "Developing and Empowering our Aspiring Leaders Act of 2022",
                "type": "S",
                "updateDateIncludingText": "2022-09-07T13:35:29Z",
                "url": "https://api.congress.gov/v3/bill/117/s/3914?format=json"
            },
            "currentChamber": "Senate",
            "currentChamberCode": "S",
            "lastSummaryUpdateDate": "2022-03-31T17:52:12Z",
            "text": " <p><strong>Developing and Empowering our Aspiring Leaders Act of 2022 </strong> </p> <p>This bill directs the Securities and Exchange Commission to revise venture capital investment regulations. Venture capital funds are exempt from certain regulations applicable to other investment firms, including those related to filings, audits, and restricted communications with investors. Under current law, non-qualifying investments—which include secondary transactions and investments in other venture capital funds—may comprise up to 20% of a venture capital fund. </p> <p>The bill allows investments acquired through secondary transactions or investments in other venture capital funds to be considered as qualifying investments for venture capital funds. However, for a private fund to qualify as a venture capital fund, the fund's investments must predominately (1) be acquired directly, or (2) be investments in other venture capital funds.</p> <p>",
            "updateDate": "2022-04-01T03:31:16Z",
            "versionCode": "00"
        }
    ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| format | The data format. Value can be xml or json. |
| offset | The starting record returned. 0 is the first record. |
| limit | The number of records returned. The maximum limit is 250. |
| fromDateTime | The starting timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |
| toDateTime | The ending timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |
| sort | Sort by update date in Congress.gov. Value can be updateDate+asc or updateDate+desc. |

### **GET `/summaries/{congress}`**

**Description**: Returns a list of summaries filtered by congress, sorted by date of last update.

**Example Request**:

```
https://api.congress.gov/v3/summaries/117?fromDateTime=2022-04-01T00:00:00Z&toDateTime=2022-04-03T00:00:00Z&sort=updateDate+desc&api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
     "summaries": [
        {
            "actionDate": "2021-02-04",
            "actionDesc": "Introduced in Senate",
            "bill": {
                "congress": 117,
                "number": "225",
                "originChamber": "Senate",
                "originChamberCode": "S",
                "title": "Competition and Antitrust Law Enforcement Reform Act of 2021",
                "type": "S",
                "updateDateIncludingText": "2022-09-29T03:41:41Z",
                "url": "https://api.congress.gov/v3/bill/117/s/225?format=json"
            },
            "currentChamber": "Senate",
            "currentChamberCode": "S",
            "lastSummaryUpdateDate": "2022-03-31T15:20:50Z",
            "text": " <p><strong>Competition and Antitrust Law Enforcement Reform Act of 2021 </strong></p> <p>This bill revises antitrust laws applicable to mergers and anticompetitive conduct. </p> <p>Specifically, the bill applies a stricter standard for permissible mergers by prohibiting mergers that (1) create an appreciable risk of materially lessening competition, or (2) unfairly lower the prices of goods or wages because of a lack of competition among buyers or employers (i.e., a monopsony). Under current law, mergers that substantially lessen competition are prohibited. </p> <p>Additionally, for some large mergers or mergers that concentrate markets beyond a certain threshold, the bill shifts the burden of proof to the merging parties to prove that the merger does not violate the law. </p> <p>The bill also prohibits exclusionary conduct that presents an appreciable risk of harming competition. </p> <p>The bill also establishes monetary penalties for violations, requires annual reporting for certain mergers and acquisitions, establishes within the Federal Trade Commission (FTC) the Office of the Competition Advocate, and sets forth whistleblower protections. </p> <p>The Government Accountability Office must report on (1) the success of merger remedies required by the Department of Justice or the FTC in recent consent decrees; and (2) the impact of mergers and acquisitions on wages, employment, innovation, and new business formation.</p>",
            "updateDate": "2022-04-01T03:31:17Z",
            "versionCode": "00"
        },
        {
            "actionDate": "2022-03-24",
            "actionDesc": "Introduced in Senate",
            "bill": {
                "congress": 117,
                "number": "3914",
                "originChamber": "Senate",
                "originChamberCode": "S",
                "title": "Developing and Empowering our Aspiring Leaders Act of 2022",
                "type": "S",
                "updateDateIncludingText": "2022-09-07T13:35:29Z",
                "url": "https://api.congress.gov/v3/bill/117/s/3914?format=json"
            },
            "currentChamber": "Senate",
            "currentChamberCode": "S",
            "lastSummaryUpdateDate": "2022-03-31T17:52:12Z",
            "text": " <p><strong>Developing and Empowering our Aspiring Leaders Act of 2022 </strong> </p> <p>This bill directs the Securities and Exchange Commission to revise venture capital investment regulations. Venture capital funds are exempt from certain regulations applicable to other investment firms, including those related to filings, audits, and restricted communications with investors. Under current law, non-qualifying investments—which include secondary transactions and investments in other venture capital funds—may comprise up to 20% of a venture capital fund. </p> <p>The bill allows investments acquired through secondary transactions or investments in other venture capital funds to be considered as qualifying investments for venture capital funds. However, for a private fund to qualify as a venture capital fund, the fund's investments must predominately (1) be acquired directly, or (2) be investments in other venture capital funds.</p> <p>",
            "updateDate": "2022-04-01T03:31:16Z",
            "versionCode": "00"
        }
    ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| congress * | The congress number. For example, the value can be 117. |
| format | The data format. Value can be xml or json. |
| offset | The starting record returned. 0 is the first record. |
| limit | The number of records returned. The maximum limit is 250. |
| fromDateTime | The starting timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |
| toDateTime | The ending timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |
| sort | Sort by update date in Congress.gov. Value can be updateDate+asc or updateDate+desc. |

### **GET `/summaries/{congress}/{billType}`**

**Description**: Returns a list of summaries filtered by congress and by bill type, sorted by date of last update.

**Example Request**:

```
https://api.congress.gov/v3/summaries/117/hr?fromDateTime=2022-04-01T00:00:00Z&toDateTime=2022-04-03T00:00:00Z&sort=updateDate+desc&api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
     "summaries": [
        {
            "actionDate": "2021-02-04",
            "actionDesc": "Introduced in Senate",
            "bill": {
                "congress": 117,
                "number": "225",
                "originChamber": "Senate",
                "originChamberCode": "S",
                "title": "Competition and Antitrust Law Enforcement Reform Act of 2021",
                "type": "S",
                "updateDateIncludingText": "2022-09-29T03:41:41Z",
                "url": "https://api.congress.gov/v3/bill/117/s/225?format=json"
            },
            "currentChamber": "Senate",
            "currentChamberCode": "S",
            "lastSummaryUpdateDate": "2022-03-31T15:20:50Z",
            "text": " <p><strong>Competition and Antitrust Law Enforcement Reform Act of 2021 </strong></p> <p>This bill revises antitrust laws applicable to mergers and anticompetitive conduct. </p> <p>Specifically, the bill applies a stricter standard for permissible mergers by prohibiting mergers that (1) create an appreciable risk of materially lessening competition, or (2) unfairly lower the prices of goods or wages because of a lack of competition among buyers or employers (i.e., a monopsony). Under current law, mergers that substantially lessen competition are prohibited. </p> <p>Additionally, for some large mergers or mergers that concentrate markets beyond a certain threshold, the bill shifts the burden of proof to the merging parties to prove that the merger does not violate the law. </p> <p>The bill also prohibits exclusionary conduct that presents an appreciable risk of harming competition. </p> <p>The bill also establishes monetary penalties for violations, requires annual reporting for certain mergers and acquisitions, establishes within the Federal Trade Commission (FTC) the Office of the Competition Advocate, and sets forth whistleblower protections. </p> <p>The Government Accountability Office must report on (1) the success of merger remedies required by the Department of Justice or the FTC in recent consent decrees; and (2) the impact of mergers and acquisitions on wages, employment, innovation, and new business formation.</p>",
            "updateDate": "2022-04-01T03:31:17Z",
            "versionCode": "00"
        },
        {
            "actionDate": "2022-03-24",
            "actionDesc": "Introduced in Senate",
            "bill": {
                "congress": 117,
                "number": "3914",
                "originChamber": "Senate",
                "originChamberCode": "S",
                "title": "Developing and Empowering our Aspiring Leaders Act of 2022",
                "type": "S",
                "updateDateIncludingText": "2022-09-07T13:35:29Z",
                "url": "https://api.congress.gov/v3/bill/117/s/3914?format=json"
            },
            "currentChamber": "Senate",
            "currentChamberCode": "S",
            "lastSummaryUpdateDate": "2022-03-31T17:52:12Z",
            "text": " <p><strong>Developing and Empowering our Aspiring Leaders Act of 2022 </strong> </p> <p>This bill directs the Securities and Exchange Commission to revise venture capital investment regulations. Venture capital funds are exempt from certain regulations applicable to other investment firms, including those related to filings, audits, and restricted communications with investors. Under current law, non-qualifying investments—which include secondary transactions and investments in other venture capital funds—may comprise up to 20% of a venture capital fund. </p> <p>The bill allows investments acquired through secondary transactions or investments in other venture capital funds to be considered as qualifying investments for venture capital funds. However, for a private fund to qualify as a venture capital fund, the fund's investments must predominately (1) be acquired directly, or (2) be investments in other venture capital funds.</p> <p>",
            "updateDate": "2022-04-01T03:31:16Z",
            "versionCode": "00"
        }
    ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| congress * | The congress number. For example, the value can be 117. |
| billType * | The type of bill. Value can be hr, s, hjres, sjres, hconres, sconres, hres, or sres. |
| format | The data format. Value can be xml or json. |
| offset | The starting record returned. 0 is the first record. |
| limit | The number of records returned. The maximum limit is 250. |
| fromDateTime | The starting timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |
| toDateTime | The ending timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |
| sort | Sort by update date in Congress.gov. Value can be updateDate+asc or updateDate+desc. |

---

## **Congress API**

### **GET `/congress`**

**Description**: Returns a list of congresses and congressional sessions.

**Example Request**:

```
https://api.congress.gov/v3/congress?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
     "congresses": [
        {
            "endYear": "2022",
            "name": "117th Congress",
            "sessions": [
                {
                    "chamber": "House of Representatives",
                    "endDate": "2022-01-03",
                    "number": 1,
                    "startDate": "2021-01-03",
                    "type": "R"
                },
                {
                    "chamber": "Senate",
                    "endDate": "2022-01-03",
                    "number": 1,
                    "startDate": "2021-01-03",
                    "type": "R"
                },
                {
                    "chamber": "House of Representatives",
                    "endDate": null,
                    "number": 2,
                    "startDate": "2022-01-03",
                    "type": "R"
                },
                {
                    "chamber": "Senate",
                    "endDate": null,
                    "number": 2,
                    "startDate": "2022-01-03",
                    "type": "R"
                }
            ],
            "startYear": "2021"
        },
        {
            "endYear": "2020",
            "name": "116th Congress",
            "sessions": [
                {
                    "chamber": "House of Representatives",
                    "endDate": "2020-01-03",
                    "number": 1,
                    "startDate": "2019-01-03",
                    "type": "R"
                },
                {
                    "chamber": "Senate",
                    "endDate": "2020-01-03",
                    "number": 1,
                    "startDate": "2019-01-03",
                    "type": "R"
                },
                {
                    "chamber": "House of Representatives",
                    "endDate": "2021-01-03",
                    "number": 2,
                    "startDate": "2020-01-03",
                    "type": "R"
                },
                {
                    "chamber": "Senate",
                    "endDate": "2021-01-03",
                    "number": 2,
                    "startDate": "2020-01-03",
                    "type": "R"
                }
            ],
            "startYear": "2019"
        }
    ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| format | The data format. Value can be xml or json. |
| offset | The starting record returned. 0 is the first record. |
| limit | The number of records returned. The maximum limit is 250. |

### **GET `/congress/{congress}`**

**Description**: Returns detailed information for a specified congress.

**Example Request**:

```
https://api.congress.gov/v3/congress/116?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
  "congress": {
      "endYear": "2020",
      "name": "116th Congress",
      "number": 116,
      "sessions": [
          {
              "chamber": "House of Representatives",
              "endDate": "2020-01-03",
              "number": 1,
              "startDate": "2019-01-03",
              "type": "R"
          },
          {
              "chamber": "Senate",
              "endDate": "2020-01-03",
              "number": 1,
              "startDate": "2019-01-03",
              "type": "R"
          },
          {
              "chamber": "House of Representatives",
              "endDate": "2021-01-03",
              "number": 2,
              "startDate": "2020-01-03",
              "type": "R"
          },
          {
              "chamber": "Senate",
              "endDate": "2021-01-03",
              "number": 2,
              "startDate": "2020-01-03",
              "type": "R"
          }
      ],
      "startYear": "2019",
      "updateDate": "2019-01-03T18:37:12Z",
      "url": "https://api.congress.gov/v3/congress/116?format=json"
  }
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| congress * | The congress number. For example, the value can be 117. |
| format | The data format. Value can be xml or json. |

### **GET `/congress/current`**

**Description**: Returns detailed information for the current congress.

**Example Request**:

```
https://api.congress.gov/v3/congress/current?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
  "congress": {
      "endYear": "2024",
      "name": "118th Congress",
      "number": 118,
      "sessions": [
          {
              "chamber": "House of Representatives",
              "endDate": "2024-01-03",
              "number": 1,
              "startDate": "2023-01-03",
              "type": "R"
          },
          {
               "chamber": "Senate",
               "endDate": "2024-01-03",
               "number": 1,
               "startDate": "2023-01-03",
               "type": "R"
          },
          {
               "chamber": "Senate",
               "number": 2,
               "startDate": "2024-01-03",
               "type": "R"
          },
          {
               "chamber": "House of Representatives",
               "number": 2,
               "startDate": "2024-01-03",
               "type": "R"
          }
      ],
      "startYear": "2023",
      "updateDate": "2023-01-03T17:43:32Z",
      "url": "https://api.congress.gov/v3/congress/current?format=json"
  }
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| format | The data format. Value can be xml or json. |

---

## **Response Codes**

* `200` – Successful operation  
* `400` – Invalid status value

---

**Note**: All responses support `application/xml` and `application/json` content types depending on the `format` parameter.

For full integration, ensure proper authentication using your API key in each request.