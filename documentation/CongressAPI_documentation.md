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

## **Members API**

### **GET `/member`**

**Description**: Returns a list of congressional members.

**Example Request**:

```
https://api.congress.gov/v3/member?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "members": [
    {
        "bioguideId": "L000174",
        "depiction": {
            "attribution": "<a href=\"http://www.senate.gov/artandhistory/history/common/generic/Photo_Collection_of_the_Senate_Historical_Office.htm\">Courtesy U.S. Senate Historical Office</a>",
            "imageUrl": "https://www.congress.gov/img/member/l000174_200.jpg"
        },
        "district": null,
        "name": "Leahy, Patrick J.",
        "partyName": "Democratic",
        "state": "Vermont",
        "terms": {
            "item": [
                {
                    "chamber": "Senate",
                    "endYear": null,
                    "startYear": 1975
                }
            ]
        },
        "updateDate": "2022-11-07T13:42:19Z",
        "url": "https://api.congress.gov/v3/member/L000174?format=json"
    },
    {
        "bioguideId": "K000377",
        "depiction": {
            "attribution": "<a href=\"http://www.senate.gov/artandhistory/history/common/generic/Photo_Collection_of_the_Senate_Historical_Office.htm\">Courtesy U.S. Senate Historical Office</a>",
            "imageUrl": "https://www.congress.gov/img/member/k000377_200.jpg"
        },
        "district": null,
        "name": "Kelly, Mark",
        "partyName": "Democratic",
        "state": "Arizona",
        "terms": {
            "item": [
                {
                    "chamber": "Senate",
                    "end": null,
                    "start": 2020
                }
            ]
        },
        "updateDate": "2023-04-01T12:42:17Z",
        "url": "https://api.congress.gov/v3/member/K000377?format=json"
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
| currentMember | The status of the member. Use true or false. |

### **GET `/member/{bioguideId}`**

**Description**: Returns detailed information for a specified congressional member.

**Example Request**:

```
https://api.congress.gov/v3/member/L000174?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "member": {
        "bioguideId": "L000174",
        "birthYear": "1940",
        "cosponsoredLegislation": {
            "count": 7520,
            "URL": "url": "https://api.congress.gov/v3/member/L000174/cosponsored-legislation"
        },
        "depiction": {
            "attribution": "<a href=\"http://www.senate.gov/artandhistory/history/common/generic/Photo_Collection_of_the_Senate_Historical_Office.htm\">Courtesy U.S. Senate Historical Office</a>",
            "imageUrl": "https://www.congress.gov/img/member/l000174_200.jpg"
        },
        "directOrderName": "Patrick J. Leahy",
        "firstName": "Patrick",
        "honorificName": "Mr.",
        "invertedOrderName": "Leahy, Patrick J.",
        "lastName": "Leahy",
        "leadership": [
            {
                "congress": 113,
                "type": "President Pro Tempore"
            },
            {
                "congress": 112,
                "type": "President Pro Tempore"
            },
            {
                "congress": 117,
                "type": "President Pro Tempore"
            }
        ],
        "partyHistory": [
            {
                "partyAbbreviation": "D",
                "partyName": "Democrat",
                "startYear": 1975
            }
        ],
        "sponsoredLegislation": {
            "count": 1768,
            "url": "https://api.congress.gov/v3/member/L000174/sponsored-legislation"
        },
        "state": "Vermont",
        "terms": [
            {
                "chamber": "Senate",
                "congress": 116,
                "endYear": 2021,
                "memberType": "Senator",
                "startYear": 2019,
                "stateCode": "VT",
                "stateName": "Vermont"
            },
            {
                "chamber": "Senate",
                "congress": 117,
                "endYear": 2023,
                "memberType": "Senator",
                "startYear": 2021,
                "stateCode": "VT",
                "stateName": "Vermont"
            }
        ],
        "updateDate": "2022-11-07T13:42:19Z"
    },
    "request": {
        "bioguideId": "l000174",
        "contentType": "application/json",
        "format": "json"
     }
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| bioguideId * | The bioguide identifier for the congressional member. For example, the value can be L000174. |
| format | The data format. Value can be xml or json. |

### **GET `/member/{bioguideId}/sponsored-legislation`**

**Description**: Returns the list of legislation sponsored by a specified congressional member.

**Example Request**:

```
https://api.congress.gov/v3/member/L000174/sponsored-legislation?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
     "sponsoredLegislation": [
        {
            "congress": 117,
            "introducedDate": "2022-06-16",
            "latestAction": {
                "actionDate": "2022-06-16",
                "text": "Read twice and referred to the Committee on the Judiciary."
            },
            "number": "4417",
            "policyArea": {
                "name": "Commerce"
            },
            "title": "Patent Trial and Appeal Board Reform Act of 2022",
            "type": "S",
            "url": "https://api.congress.gov/v3/bill/117/s/4417?format=json"
        },
        {
            "congress": 117,
            "introducedDate": "2022-06-09",
            "latestAction": {
                "actionDate": "2022-06-09",
                "text": "Read twice and referred to the Committee on the Judiciary."
            },
            "number": "4373",
            "policyArea": {
                "name": "Crime and Law Enforcement"
            },
            "title": "NDO Fairness Act",
            "type": "S",
            "url": "https://api.congress.gov/v3/bill/117/s/4373?format=json"
        }
    ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| bioguideId * | The bioguide identifier for the congressional member. For example, the value can be L000174. |
| format | The data format. Value can be xml or json. |
| offset | The starting record returned. 0 is the first record. |
| limit | The number of records returned. The maximum limit is 250. |

### **GET `/member/{bioguideId}/cosponsored-legislation`**

**Description**: Returns the list of legislation cosponsored by a specified congressional member.

**Example Request**:

```
https://api.congress.gov/v3/member/L000174/cosponsored-legislation?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
     "cosponsoredLegislation": [
        {
            "congress": 117,
            "introducedDate": "2021-05-11",
            "latestAction": {
                "actionDate": "2021-04-22",
                "text": "Read twice and referred to the Committee on Finance."
            },
            "number": "1315",
            "policyArea": {
                "name": "Health"
            },
            "title": "Lymphedema Treatment Act",
            "type": "S",
            "url": "https://api.congress.gov/v3/bill/117/s/1315?format=json"
        },
        {
            "congress": 117,
            "introducedDate": "2021-02-22",
            "latestAction": {
                "actionDate": "2021-03-17",
                "text": "Referred to the Committee on Armed Services."
            },
            "number": "344",
            "policyArea": {
                "name": "Armed Forces and National Security"
            },
            "title": "Major Richard Star Act",
            "type": "S",
            "url": "https://api.congress.gov/v3/bill/117/s/344?format=json"
        }
    ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| bioguideId * | The bioguide identifier for the congressional member. For example, the value can be L000174. |
| format | The data format. Value can be xml or json. |
| offset | The starting record returned. 0 is the first record. |
| limit | The number of records returned. The maximum limit is 250. |

### **GET `/member/congress/{congress}`**

**Description**: Returns the list of members specified by Congress.

**Example Request**:

```
https://api.congress.gov/v3/member/congress/118?api_key=[INSERT_KEY]
```

**Example Request for a previous Congress**:

```
https://api.congress.gov/v3/member/congress/117?currentMember=False&api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "members": [
    {
        "bioguideId": "B001320",
        "depiction": {
            "attribution": "Image courtesy of the Senator's office",
            "imageUrl": "https://www.congress.gov/img/member/b001320_200.jpg"
    },
        "name": "Butler, Laphonza R.",
        "partyName": "Democratic",
        "state": "California",
        "terms": {
            "item": [
                {
                    "chamber": "Senate",
                    "startYear": 2023
                }
            ]
        },
        "updateDate": "2024-04-09T15:54:25Z",
        "url": "http://api.congress.gov/v3/member/B001320?format=json"
    },
    {
         "bioguideId": "A000376",
         "depiction": {
             "attribution": "Image courtesy of the Member",
             "imageUrl": "https://www.congress.gov/img/member/a000376_200.jpg"
    },
          "district": 32,
          "name": "Allred, Colin Z.",
          "partyName": "Democratic",
          "state": "Texas",
          "terms": {
              "item": [
                  {
                      "chamber": "House of Representatives",
                      "startYear": 2019
                  }
              ]
          },
         "updateDate": "2024-04-09T13:26:21Z",
         "url": "http://api.congress.gov/v3/member/A000376?format=json"
    }
  ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| congress * | The congress number. For example, the value can be 118. |
| format | The data format. Value can be xml or json. |
| offset | The starting record returned. 0 is the first record. |
| limit | The number of records returned. The maximum limit is 250. |
| currentMember | The status of the member. Use true or false. Use currentMember=false for the most accurate calls for past Congresses. |

### **GET `/member/{stateCode}`**

**Description**: Returns a list of members filtered by state.

**Example Request**:

```
https://api.congress.gov/v3/member/MI?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
   "members": [
   {
       "bioguideId": "J000307",
       "depiction": {
           "attribution": "Image courtesy of the Member",
           "imageUrl": "https://www.congress.gov/img/member/j000307_200.jpg"
   },
       "district": 10,
       "name": "James, John",
       "partyName": "Republican",
       "state": "Michigan",
       "terms": {
           "item": [
               {
                   "chamber": "House of Representatives",
                   "startYear": 2023
               }
           ]
       },
       "updateDate": "2024-03-22T18:36:13Z",
       "url": "http://api.congress.gov/v3/member/J000307?format=json"
   }
   ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| stateCode * | The two letter identifier for the state the member represents. For example, the value can be MI for Michigan. |
| format | The data format. Value can be xml or json. |
| currentMember | The status of the member. Use true or false. Use currentMember=True for the current congress data only. |

### **GET `/member/{stateCode}/{district}`**

**Description**: Returns a list of members filtered by state and district.

**Example Request**:

```
https://api.congress.gov/v3/member/MI/10?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
 "members": [
 {
     "bioguideId": "J000307",
     "depiction": {
         "attribution": "Image courtesy of the Member",
         "imageUrl": "https://www.congress.gov/img/member/j000307_200.jpg"
 },
     "district": 10,
     "name": "James, John",
     "partyName": "Republican",
     "state": "Michigan",
     "terms": {
         "item": [
             {
                 "chamber": "House of Representatives",
                 "startYear": 2023
             }
         ]
     },
     "updateDate": "2024-03-22T18:36:13Z",
     "url": "http://api.congress.gov/v3/member/J000307?format=json"
  }
 ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| stateCode * | The two letter identifier for the state the member represents. For example, the value can be MI for Michigan. |
| district * | The district number for the district the member represents. For example, the value can be 10. |
| format | The data format. Value can be xml or json. |
| currentMember | The status of the member. Use true or false. Use currentMember=True for the current congress data only. |

### **GET `/member/congress/{congress}/{stateCode}/{district}`**

**Description**: Returns a list of members filtered by congress, state and district.

**Example Request**:

```
https://api.congress.gov/v3/member/congress/118/MI/10?currentMember=True&api_key=[INSERT_KEY]
```

**Example Request for a previous Congress**:

```
https://api.congress.gov/v3/member/congress/97/TX/10?currentMember=False&api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
 "members": [
 {
     "bioguideId": "J000307",
     "depiction": {
         "attribution": "Image courtesy of the Member",
         "imageUrl": "https://www.congress.gov/img/member/j000307_200.jpg"
 },
     "district": 10,
     "name": "James, John",
     "partyName": "Republican",
     "state": "Michigan",
     "terms": {
         "item": [
             {
                 "chamber": "House of Representatives",
                 "startYear": 2023
             }
         ]
     },
     "updateDate": "2024-03-22T18:36:13Z",
     "url": "http://api.congress.gov/v3/member/J000307?format=json"
   }
 ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| congress * | The Congress number. For example, 118. |
| stateCode * | The two letter identifier for the state the member represents. For example, the value can be MI for Michigan. |
| district * | The district number for the district the member represents. For example, the value can be 10. |
| format | The data format. Value can be xml or json. |
| currentMember | The status of the member. Use true or false. Use currentMember=True for the current congress data only. |

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
            "startYear": "2021"
        },
        {
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

---

## **[BETA] House Vote API Documentation**

Returns House of Representatives roll call vote data from the API. These endpoints are currently in beta.

Base URL: `https://api.congress.gov/v3/house-vote`

All endpoints require an API key provided via `?api_key=[INSERT_KEY]`.

---

### **GET `/house-vote`**

**Description**: Returns House of Representatives roll call vote data from the API. This endpoint is currently in beta.

**Example Request**:

`https://api.congress.gov/v3/house-vote?api_key=[INSERT_KEY]`

**Example Response**:

```json
{
    "houseRollCallVotes": [
        {
           "congress": 119,
           "identifier": 1191202517,
           "legislationNumber": "30",
           "legislationType": "HR",
           "legislationUrl": "https://congress.gov/bill/119/house-bill/30",
           "result": "Passed",
           "rollCallNumber": 17,
           "sessionNumber": 1,
           "sourceDataURL": "https://clerk.house.gov/evs/2025/roll017.xml",
           "startDate": "2025-01-16T11:00:00-05:00",
           "updateDate": "2025-04-18T08:44:47-04:00",
           "url": "https://api.congress.gov/v3/house-vote/119/1/17",
           "voteType": "Yea-and-Nay"
        }
    ]
 }
```

**Query Parameters**:

*   `format` (string): The data format. Value can be xml or json.
*   `offset` (integer): The starting record returned. 0 is the first record.
*   `limit` (integer): The number of records returned. The maximum limit is 250.

---

### **GET `/house-vote/{congress}`**

**Description**: Returns House of Representatives roll call vote data from the API filtered by the specified Congress. This endpoint is currently in beta.

**Example Request**:

`https://api.congress.gov/v3/house-vote/119?api_key=[INSERT_KEY]`

**Example Response**:

```json
{
    "houseRollCallVotes": [
        {
           "congress": 119,
           "identifier": 1191202517,
           "legislationNumber": "30",
           "legislationType": "HR",
           "legislationUrl": "https://congress.gov/bill/119/house-bill/30",
           "result": "Passed",
           "rollCallNumber": 17,
           "sessionNumber": 1,
           "sourceDataURL": "https://clerk.house.gov/evs/2025/roll017.xml",
           "startDate": "2025-01-16T11:00:00-05:00",
           "updateDate": "2025-04-18T08:44:47-04:00",
           "url": "https://api.congress.gov/v3/house-vote/119/1/17",
           "voteType": "Yea-and-Nay"
        }
    ]
 }
```

**Path Parameters**:

*   `congress` (integer): The congress number. For example, the value can be 119.

**Query Parameters**:

*   `format` (string): The data format. Value can be xml or json.
*   `offset` (integer): The starting record returned. 0 is the first record.
*   `limit` (integer): The number of records returned. The maximum limit is 250.

---

### **GET `/house-vote/{congress}/{session}`**

**Description**: Returns House of Representatives roll call vote data from the API filtered by the specified Congress and session. This endpoint is currently in beta.

**Example Request**:

`https://api.congress.gov/v3/house-vote/119/1?api_key=[INSERT_KEY]`

**Example Response**:

```json
{
    "houseRollCallVotes": [
        {
           "congress": 119,
           "identifier": 1191202517,
           "legislationNumber": "30",
           "legislationType": "HR",
           "legislationUrl": "https://congress.gov/bill/119/house-bill/30",
           "result": "Passed",
           "rollCallNumber": 17,
           "sessionNumber": 1,
           "sourceDataURL": "https://clerk.house.gov/evs/2025/roll017.xml",
           "startDate": "2025-01-16T11:00:00-05:00",
           "updateDate": "2025-04-18T08:44:47-04:00",
           "url": "https://api.congress.gov/v3/house-vote/119/1/17",
           "voteType": "Yea-and-Nay"
        }
    ]
 }
```

**Path Parameters**:

*   `congress` (integer): The congress number. For example, the value can be 119.
*   `session` (integer): The session number. The value can be 1 or 2.

**Query Parameters**:

*   `format` (string): The data format. Value can be xml or json.
*   `offset` (integer): The starting record returned. 0 is the first record.
*   `limit` (integer): The number of records returned. The maximum limit is 250.

---

### **GET `/house-vote/{congress}/{session}/{voteNumber}`**

**Description**: Returns detailed information for a specified House of Representatives roll call vote. This endpoint is currently in beta.

**Example Request**:

`https://api.congress.gov/v3/house-vote/119/1/17?api_key=[INSERT_KEY]`

**Example Response**:

```json
{
  "houseRollCallVote": [
    {
        "congress": 119,
        "identifier": 1191202517,
        "legislationNumber": "30",
        "legislationType": "HR",
        "legislationUrl": "https://congress.gov/bill/119/house-bill/30",
        "result": "Passed",
        "rollCallNumber": 17,
        "sessionNumber": 1,
        "sourceDataURL": "https://clerk.house.gov/evs/2025/roll017.xml",
        "startDate": "2025-01-16T11:00:00-05:00",
        "updateDate": "2025-04-18T08:44:47-04:00",
        "votePartyTotal": [
            {
                 "nayTotal": 0,
                 "notVotingTotal": 6,
                 "party": {
                     "name": "Republican",
                     "type": "R"
            },
                 "presentTotal": 0,
                 "voteParty": "R",
                 "yeaTotal": 213
            },
            {
                 "nayTotal": 145,
                 "notVotingTotal": 9,
                 "party": {
                     "name": "Democrat",
                     "type": "D"
            },
                 "presentTotal": 0,
                 "voteParty": "D",
                 "yeaTotal": 61
            },
            {
                 "nayTotal": 0,
                 "notVotingTotal": 0,
                 "party": {
                     "name": "Independent",
                     "type": "I"
            },
                 "presentTotal": 0,
                 "voteParty": "I",
                 "yeaTotal": 0
            }
       ],
       "voteQuestion": "On Passage",
       "voteType": "Yea-and-Nay"
  }
]
}
```

**Path Parameters**:

*   `congress` (integer): The congress number. For example, the value can be 119.
*   `session` (integer): The session number. The value can be 1 or 2.
*   `voteNumber` (integer): The assigned roll call vote number. For example, 17.

**Query Parameters**:

*   `format` (string): The data format. Value can be xml or json.
*   `offset` (integer): The starting record returned. 0 is the first record.
*   `limit` (integer): The number of records returned. The maximum limit is 250.

---

### **GET `/house-vote/{congress}/{session}/{voteNumber}/members`**

**Description**: Returns detailed information for how members voted on a specified House of Representatives roll call vote. This endpoint is currently in beta.

**Example Request**:

`https://api.congress.gov/v3/house-vote/119/1/17/members?api_key=[INSERT_KEY]`

**Example Response**:

```json
{
  "houseRollCallMemberVotes": [
    {
        "congress": 119,
        "identifier": 1191202517,
        "legislationNumber": "30",
        "legislationType": "HR",
        "legislationUrl": "https://congress.gov/bill/119/house-bill/30",
        "results": [
            {
              "bioguideID": "A000055",
              "firstName": "Robert",
              "lastName": "Aderholt",
              "voteCast": "Yea",
              "voteParty": "R",
              "voteState": "AL"
            },
            {
              "bioguideID": "A000148",
              "firstName": "Jake",
              "lastName": "Auchincloss",
              "voteCast": "Nay",
              "voteParty": "D",
              "voteState": "MA"
            }
       ],
       "result": "Passed",
       "rollCallNumber": 17,
       "sessionNumber": 1,
       "sourceDataURL": "https://clerk.house.gov/evs/2025/roll017.xml",
       "startDate": "2025-01-16T11:00:00-05:00",
       "updateDate": "2025-04-18T08:44:47-04:00",
       "voteQuestion": "On Passage",
       "voteType": "Yea-and-Nay"
  }
]
}
```

**Path Parameters**:

*   `congress` (integer): The congress number. For example, the value can be 119.
*   `session` (integer): The session number. The value can be 1 or 2.
*   `voteNumber` (integer): The assigned roll call vote number. For example, 17.

**Query Parameters**:

*   `format` (string): The data format. Value can be xml or json.
*   `offset` (integer): The starting record returned. 0 is the first record.
*   `limit` (integer): The number of records returned. The maximum limit is 250.

---

## **Congress.gov Committee API Documentation**

## **Overview**

The Congress.gov Committee API provides structured access to congressional committee data, including committee details, subcommittees, bills referred to committees, reports, nominations, and communications.

Base URL: `https://api.congress.gov/v3/committee`

All endpoints require an API key provided via `?api_key=[INSERT_KEY]`.

---

## **Endpoints**

### **GET `/committee`**

**Description**: Returns a list of congressional committees.

**Example Request**:

```
https://api.congress.gov/v3/committee?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
     "committees": [
        {
            "chamber": "House",
            "committeeTypeCode": "Standing",
            "updateDate": "2020-02-04T00:07:37Z",
            "name": "Transportation and Infrastructure Committee",
            "parent": null,
            "subcommittees": [
                {
                    "name": "Investigations and Oversight Subcommittee",
                    "systemCode": "hspw01",
                    "url": "https://api.congress.gov/v3/committee/house/hspw01?format=json"
                },
                {
                    "name": "Aviation Subcommittee",
                    "systemCode": "hspw05",
                    "url": "https://api.congress.gov/v3/committee/house/hspw05?format=json"
                }
            ],
            "systemCode": "hspw00",
            "url": "https://api.congress.gov/v3/committee/house/hspw00?format=json"
        }
     ]
}
```

**Query Parameters**:

| Name | Description |
|------|-------------|
| format | The data format. Value can be xml or json. |
| offset | The starting record returned. 0 is the first record. |
| limit | The number of records returned. The maximum limit is 250. |
| fromDateTime | The starting timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |
| toDateTime | The ending timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |

---

### **GET `/committee/{chamber}`**

**Description**: Returns a list of congressional committees filtered by the specified chamber.

**Example Request**:

```
https://api.congress.gov/v3/committee/house?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
     "committees": [
        {
            "chamber": "House",
            "committeeTypeCode": "Standing",
            "name": "Transportation and Infrastructure Committee",
            "parent": null,
            "subcommittees": [
                {
                    "name": "Investigations and Oversight Subcommittee",
                    "systemCode": "hspw01",
                    "url": "https://api.congress.gov/v3/committee/house/hspw01?format=json"
                },
                {
                    "name": "Aviation Subcommittee",
                    "systemCode": "hspw05",
                    "url": "https://api.congress.gov/v3/committee/house/hspw05?format=json"
                }
            ],
            "systemCode": "hspw00",
            "url": "https://api.congress.gov/v3/committee/house/hspw00?format=json"
        }
     ]
}
```

**Path Parameters**:

* `chamber` (string): The chamber name. Value can be house, senate, or joint.

**Query Parameters**:

| Name | Description |
|------|-------------|
| format | The data format. Value can be xml or json. |
| offset | The starting record returned. 0 is the first record. |
| limit | The number of records returned. The maximum limit is 250. |
| fromDateTime | The starting timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |
| toDateTime | The ending timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |

---

### **GET `/committee/{congress}`**

**Description**: Returns a list of congressional committees filtered by the specified congress.

**Example Request**:

```
https://api.congress.gov/v3/committee/117?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
     "committees": [
        {
            "chamber": "House",
            "committeeTypeCode": "Standing",
            "name": "Transportation and Infrastructure Committee",
            "parent": null,
            "subcommittees": [
                {
                    "name": "Investigations and Oversight Subcommittee",
                    "systemCode": "hspw01",
                    "url": "https://api.congress.gov/v3/committee/house/hspw01?format=json"
                }
            ],
            "systemCode": "hspw00",
            "url": "https://api.congress.gov/v3/committee/house/hspw00?format=json"
        }
     ]
}
```

**Path Parameters**:

* `congress` (integer): The congress number. For example, the value can be 117.

**Query Parameters**:

| Name | Description |
|------|-------------|
| format | The data format. Value can be xml or json. |
| offset | The starting record returned. 0 is the first record. |
| limit | The number of records returned. The maximum limit is 250. |
| fromDateTime | The starting timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |
| toDateTime | The ending timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |

---

### **GET `/committee/{congress}/{chamber}`**

**Description**: Returns a list of committees filtered by the specified congress and chamber.

**Example Request**:

```
https://api.congress.gov/v3/committee/117/house?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
     "committees": [
        {
            "chamber": "House",
            "committeeTypeCode": "Standing",
            "name": "Transportation and Infrastructure Committee",
            "parent": null,
            "subcommittees": [
                {
                    "name": "Investigations and Oversight Subcommittee",
                    "systemCode": "hspw01",
                    "url": "https://api.congress.gov/v3/committee/house/hspw01?format=json"
                }
            ],
            "systemCode": "hspw00",
            "url": "https://api.congress.gov/v3/committee/house/hspw00?format=json"
        }
     ]
}
```

**Path Parameters**:

* `congress` (integer): The congress number. For example, the value can be 117.
* `chamber` (string): The chamber name. Value can be house, senate, or joint.

**Query Parameters**:

| Name | Description |
|------|-------------|
| format | The data format. Value can be xml or json. |
| offset | The starting record returned. 0 is the first record. |
| limit | The number of records returned. The maximum limit is 250. |
| fromDateTime | The starting timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |
| toDateTime | The ending timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |

---

### **GET `/committee/{chamber}/{committeeCode}`**

**Description**: Returns detailed information for a specified congressional committee.

**Example Request**:

```
https://api.congress.gov/v3/committee/house/hspw00?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "committee": {
        "bills": {
            "count": 25384,
            "url": "https://api.congress.gov/v3/committee/house/hspw00/bills?format=json"
        },
        "communications": {
            "count": 6775,
            "url": "https://api.congress.gov/v3/committee/house/hspw00/house-communication?format=json"
        },
        "history": [
            {
                "libraryOfCongressName": "Transportation and Infrastructure",
                "officialName": "Committee on Transportation and Infrastructure",
                "startDate": "1995-01-04T05:00:00Z",
                "updateDate": "2020-02-14T19:13:07Z"
            },
            {
                "endDate": "1995-01-03T05:00:00Z",
                "libraryOfCongressName": "Public Works and Transportation",
                "officialName": "Committee on Public Works and Transportation",
                "startDate": "1975-01-01T05:00:00Z",
                "updateDate": "2020-02-10T16:49:05Z"
            }
        ],
        "isCurrent": true,
        "reports": {
            "count": 1382,
            "url": "https://api.congress.gov/v3/committee/house/hspw00/reports?format=json"
        },
        "subcommittees": [
            {
                "name": "Investigations and Oversight Subcommittee",
                "systemCode": "hspw01",
                "url": "https://api.congress.gov/v3/committee/house/hspw01?format=json"
            },
            {
                "name": "Aviation Subcommittee",
                "systemCode": "hspw05",
                "url": "https://api.congress.gov/v3/committee/house/hspw05?format=json"
            }
        ],
        "systemCode": "hspw00",
        "type": "Standing",
        "updateDate": "2020-02-04T00:07:37Z"
    }
}
```

**Path Parameters**:

* `chamber` (string): The chamber name. Value can be house, senate, or joint.
* `committeeCode` (string): The committee code for the committee. For example, the value can be hspw00.

**Query Parameters**:

| Name | Description |
|------|-------------|
| format | The data format. Value can be xml or json. |

---

### **GET `/committee/{chamber}/{committeeCode}/bills`**

**Description**: Returns the list of legislation associated with the specified congressional committee.

**Example Request**:

```
https://api.congress.gov/v3/committee/house/hspw00/bills?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "committee-bills": {
        "bills": [
            {
                "actionDate": "2012-04-19T13:01:00Z",
                "congress": 112,
                "number": "117",
                "relationshipType": "Referred to",
                "type": "HCONRES",
                "updateDate": "2019-02-17T21:10:13Z",
                "url": "https://api.congress.gov/v3/bill/112/hconres/117?format=json"
            },
            {
                "actionDate": "2012-02-08T14:51:00Z",
                "congress": 112,
                "number": "543",
                "relationshipType": "Referred to",
                "type": "HRES",
                "updateDate": "2019-02-17T21:05:25Z",
                "url": "https://api.congress.gov/v3/bill/112/hres/543?format=json"
            }
        ]
    }
}
```

**Path Parameters**:

* `chamber` (string): The chamber name. Value can be house, senate, or joint.
* `committeeCode` (string): The committee code for the committee. For example, the value can be hspw00.

**Query Parameters**:

| Name | Description |
|------|-------------|
| format | The data format. Value can be xml or json. |
| offset | The starting record returned. 0 is the first record. |
| limit | The number of records returned. The maximum limit is 250. |
| fromDateTime | The starting timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |
| toDateTime | The ending timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |

---

### **GET `/committee/{chamber}/{committeeCode}/reports`**

**Description**: Returns the list of committee reports associated with a specified congressional committee.

**Example Request**:

```
https://api.congress.gov/v3/committee/house/hspw00/reports?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "reports": [
        {
            "chamber": "House",
            "citation": "H. Rept. 109-570",
            "congress": 109,
            "number": 570,
            "part": 1,
            "type": "HRPT",
            "updateDate": "2015-03-20 00:04:12+00:00",
            "url": "https://api.congress.gov/v3/committee-report/109/HRPT/570?format=json"
        },
        {
            "chamber": "House",
            "citation": "H. Rept. 109-121",
            "congress": 109,
            "number": 121,
            "part": 1,
            "type": "HRPT",
            "updateDate": "2015-03-20 00:06:53+00:00",
            "url": "https://api.congress.gov/v3/committee-report/109/HRPT/121?format=json"
        }
    ]
}
```

**Path Parameters**:

* `chamber` (string): The chamber name. Value can be house, senate, or joint.
* `committeeCode` (string): The committee code for the committee. For example, the value can be hspw00.

**Query Parameters**:

| Name | Description |
|------|-------------|
| format | The data format. Value can be xml or json. |
| offset | The starting record returned. 0 is the first record. |
| limit | The number of records returned. The maximum limit is 250. |
| fromDateTime | The starting timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |
| toDateTime | The ending timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |

---

### **GET `/committee/{chamber}/{committeeCode}/nominations`**

**Description**: Returns the list of nominations associated with a specified congressional committee.

**Example Request**:

```
https://api.congress.gov/v3/committee/senate/ssas00/nominations?format=json&api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "nominations": [
        {
            "citation": "PN2477",
            "congress": 117,
            "description": " ",
            "latestAction": {
                "actionDate": "2022-09-29",
                "text": "Confirmed by the Senate by Voice Vote."
            },
            "nominationType": {
                "isCivilian": false,
                "isMilitary": true
            },
            "number": 2477,
            "partNumber": "00",
            "receivedDate": "2022-08-03",
            "updateDate": "2022-09-30 04:40:14+00:00",
            "url": "https://api.congress.gov/v3/nomination/117/2477?format=json"
        },
        {
            "citation": "PN2486",
            "congress": 117,
            "description": " ",
            "latestAction": {
                "actionDate": "2022-09-29",
                "text": "Confirmed by the Senate by Voice Vote."
            },
            "nominationType": {
                "isCivilian": false,
                "isMilitary": true
            },
            "number": 2486,
            "partNumber": "00",
            "receivedDate": "2022-08-03",
            "updateDate": "2022-09-30 04:40:15+00:00",
            "url": "https://api.congress.gov/v3/nomination/117/2486?format=json"
        }
    ]
}
```

**Path Parameters**:

* `chamber` (string): The chamber name. Value will be senate.
* `committeeCode` (string): The committee code for the committee. For example, the value can be ssas00.

**Query Parameters**:

| Name | Description |
|------|-------------|
| format | The data format. Value can be xml or json. |
| offset | The starting record returned. 0 is the first record. |
| limit | The number of records returned. The maximum limit is 250. |

---

### **GET `/committee/{chamber}/{committeeCode}/house-communication`**

**Description**: Returns the list of House communications associated with a specified congressional committee.

**Example Request**:

```
https://api.congress.gov/v3/committee/house/hspw00/house-communication?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
  "houseCommunications": [
        {
            "chamber": "House",
            "communicationType": {
                "code": "EC",
                "name": "Executive Communication"
            },
            "congress": 114,
            "number": 3262,
            "referralDate": "2015-10-27",
            "updateDate": "2018-02-02",
            "url": "https://api.congress.gov/v3/house-communication/114/ec/3262?format=json"
        },
        {
            "chamber": "House",
            "communicationType": {
                "code": "EC",
                "name": "Executive Communication"
            },
            "congress": 115,
            "number": 3263,
            "referralDate": "2015-10-27",
            "updateDate": "2018-02-02",
            "url": "https://api.congress.gov/v3/house-communication/114/ec/3263?format=json"
        }
    ]
}
```

**Path Parameters**:

* `chamber` (string): The chamber name. Value will be house.
* `committeeCode` (string): The committee code for the committee. For example, the value can be hspw00.

**Query Parameters**:

| Name | Description |
|------|-------------|
| format | The data format. Value can be xml or json. |
| offset | The starting record returned. 0 is the first record. |
| limit | The number of records returned. The maximum limit is 250. |

---

### **GET `/committee/{chamber}/{committeeCode}/senate-communication`**

**Description**: Returns the list of Senate communications associated with a specified congressional committee.

**Example Request**:

```
https://api.congress.gov/v3/committee/senate/ssas00/senate-communication?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
  "senateCommunications": [
        {
            "chamber": "Senate",
            "communicationType": {
                "code": "EC",
                "name": "Executive Communication"
            },
            "congress": 114,
            "number": 7402,
            "referralDate": "2016-11-16",
            "updateDate": "2017-01-06",
            "url": "https://api.congress.gov/v3/senate-communication/114/ec/7402?format=json"
        },
        {
            "chamber": "Senate",
            "communicationType": {
                "code": "EC",
                "name": "Executive Communication"
            },
            "congress": 114,
            "number": 7403,
            "referralDate": "2016-11-16",
            "updateDate": "2017-01-06",
            "url": "https://api.congress.gov/v3/senate-communication/114/ec/7403?format=json"
        }
    ]
}
```

**Path Parameters**:

* `chamber` (string): The chamber name. Value will be senate.
* `committeeCode` (string): The committee code for the committee. For example, the value can be ssas00.

**Query Parameters**:

| Name | Description |
|------|-------------|
| format | The data format. Value can be xml or json. |
| offset | The starting record returned. 0 is the first record. |
| limit | The number of records returned. The maximum limit is 250. |

---

## **Committee Report API**

**Overview**

Returns committee report data from the API.

Base URL: `https://api.congress.gov/v3/committee-report`

All endpoints require an API key provided via `?api_key=[INSERT_KEY]`.

---

### **GET `/committee-report`**

**Description**: Returns a list of committee reports.

**Example Request**:

```
https://api.congress.gov/v3/committee-report?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
      "reports": [
        {
            "chamber": "House",
            "citation": "H. Rept. 117-397,Part 2",
            "congress": 117,
            "number": 397,
            "part": 2,
            "type": "HRPT",
            "updateDate": "2022-09-29 03:27:29+00:00",
            "url": "https://api.congress.gov/v3/committee-report/117/HRPT/397?format=json"
        },
        {
            "chamber": "House",
            "citation": "H. Rept. 117-397",
            "congress": 117,
            "number": 397,
            "part": 1,
            "type": "HRPT",
            "updateDate": "2022-09-29 03:27:29+00:00",
            "url": "https://api.congress.gov/v3/committee-report/117/HRPT/397?format=json"
        }
    ]
}
```

**Query Parameters**:

| Name         | Description                                                                    |
|--------------|--------------------------------------------------------------------------------|
| `format`     | string (query) - The data format. Value can be xml or json.                    |
| `conference` | string (query) - Flag to indicate conference reports. Value can be true or false. |
| `offset`     | integer (query) - The starting record returned. 0 is the first record.         |
| `limit`      | integer (query) - The number of records returned. The maximum limit is 250.    |
| `fromDateTime` | string (query) - The starting timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |
| `toDateTime`   | string (query) - The ending timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z.   |

---

### **GET `/committee-report/{congress}`**

**Description**: Returns a list of committee reports filtered by the specified congress.

**Example Request**:

```
https://api.congress.gov/v3/committee-report/116?conference=true&api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "reports": [
        {
            "chamber": "House",
            "citation": "H. Rept. 116-617",
            "congress": 116,
            "number": 617,
            "part": 1,
            "type": "HRPT",
            "updateDate": "2022-05-20 16:27:57+00:00",
            "url": "https://api.congress.gov/v3/committee-report/116/HRPT/617?format=json"
        }
    ]
}
```

**Path Parameters**:

| Name       | Description                                           |
|------------|-------------------------------------------------------|
| `congress` * | integer (path) - The congress number. E.g., 116. |

**Query Parameters**: Same as for `/committee-report`.

---

### **GET `/committee-report/{congress}/{reportType}`**

**Description**: Returns a list of committee reports filtered by the specified congress and report type.

**Example Request**:

```
https://api.congress.gov/v3/committee-report/116/hrpt?conference=true&api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "reports": [
        {
            "chamber": "House",
            "citation": "H. Rept. 116-617",
            "congress": 116,
            "number": 617,
            "part": 1,
            "type": "HRPT",
            "updateDate": "2022-05-20 16:27:57+00:00",
            "url": "https://api.congress.gov/v3/committee-report/116/HRPT/617?format=json"
        }
    ]
}
```

**Path Parameters**:

| Name         | Description                                                              |
|--------------|--------------------------------------------------------------------------|
| `congress` *   | integer (path) - The congress number. E.g., 116.                       |
| `reportType` * | string (path) - The type of committee report. Value can be hrpt, srpt, or erpt. |

**Query Parameters**: Same as for `/committee-report`.

---

### **GET `/committee-report/{congress}/{reportType}/{reportNumber}`**

**Description**: Returns detailed information for a specified committee report.

**Example Request**:

```
https://api.congress.gov/v3/committee-report/116/HRPT/617?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "committeeReports": [
        {
            "associatedBill": [
                {
                    "congress": 116,
                    "number": "6395",
                    "type": "HR",
                    "url": "https://api.congress.gov/v3/bill/116/hr/6395?format=json"
                }
            ],
            "chamber": "House",
            "citation": "H. Rept. 116-617",
            "congress": 116,
            "isConferenceReport": true,
            "issueDate": "2020-12-03T05:00:00Z",
            "number": 617,
            "part": 1,
            "reportType": "H.Rept.",
            "sessionNumber": 2,
            "text": {
              "count": 2,
              "url": "https://api.congress.gov/v3/committee-report/116/hrpt/617/text?format=json"
            },
            "title": "WILLIAM M. (MAC) THORNBERRY NATIONAL DEFENSE AUTHORIZATION ACT FOR FISCAL YEAR 2021",
            "type": "HRPT",
            "updateDate": "2022-05-20T16:27:57Z"
        }
    ]
}
```

**Path Parameters**:

| Name           | Description                                                              |
|----------------|--------------------------------------------------------------------------|
| `congress` *     | integer (path) - The congress number. E.g., 116.                       |
| `reportType` *   | string (path) - The type of committee report. Value can be hrpt, srpt, or erpt. |
| `reportNumber` * | integer (path) - The committee report’s assigned number. E.g., 617.    |

**Query Parameters**:

| Name     | Description                                                       |
|----------|-------------------------------------------------------------------|
| `format` | string (query) - The data format. Value can be xml or json.       |

---

### **GET `/committee-report/{congress}/{reportType}/{reportNumber}/text`**

**Description**: Returns the list of texts for a specified committee report.

**Example Request**:

```
https://api.congress.gov/v3/committee-report/116/hrpt/617/text?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "text": [
        {
            "formats": [
                {
                    "isErrata": "N",
                    "type": "Formatted Text",
                    "url": "https://www.congress.gov/116/crpt/hrpt617/generated/CRPT-116hrpt617.htm"
                }
            ]
        },
        {
            "formats": [
                {
                    "isErrata": "N",
                    "type": "PDF",
                    "url": "https://www.congress.gov/116/crpt/hrpt617/CRPT-116hrpt617.pdf"
                }
            ]
        }
    ]
}
```

**Path Parameters**:

| Name           | Description                                                              |
|----------------|--------------------------------------------------------------------------|
| `congress` *     | integer (path) - The congress number. E.g., 116.                       |
| `reportType` *   | string (path) - The type of committee report. Value can be hrpt, srpt, or erpt. |
| `reportNumber` * | integer (path) - The committee report’s assigned number. E.g., 617.    |

**Query Parameters**:

| Name     | Description                                                                    |
|----------|--------------------------------------------------------------------------------|
| `format` | string (query) - The data format. Value can be xml or json.                    |
| `offset` | integer (query) - The starting record returned. 0 is the first record.         |
| `limit`  | integer (query) - The number of records returned. The maximum limit is 250.    |

---

## **Committee Print API**

### **GET `/committee-print`**

**Description**: Returns a list of committee prints.

**Example Request**:

```
https://api.congress.gov/v3/committee-print?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "committeePrints": [
        {
            "chamber": "House",
            "congress": 117,
            "jacketNumber": 48144,
            "updateDate": "2022-08-01 21:19:33+00:00",
            "url": "https://api.congress.gov/v3/committee-print/117/house/48144?format=json"
        },
        {
            "chamber": "House",
            "congress": 117,
            "jacketNumber": 48031,
            "updateDate": "2022-10-19 21:15:20+00:00",
            "url": "https://api.congress.gov/v3/committee-print/117/house/48031?format=json"
        }
    ]
}
```

**Query Parameters**:

| Name | Description |
|------|-------------|
| `format` | string (query) - The data format. Value can be xml or json. |
| `offset` | integer (query) - The starting record returned. 0 is the first record. |
| `limit` | integer (query) - The number of records returned. The maximum limit is 250. |
| `fromDateTime` | string (query) - The starting timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |
| `toDateTime` | string (query) - The ending timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |

---

### **GET `/committee-print/{congress}`**

**Description**: Returns a list of committee prints filtered by the specified congress.

**Example Request**:

```
https://api.congress.gov/v3/committee-print/117?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "committeePrints": [
        {
            "chamber": "House",
            "congress": 117,
            "jacketNumber": 48144,
            "updateDate": "2022-08-01 21:19:33+00:00",
            "url": "https://api.congress.gov/v3/committee-print/117/house/48144?format=json"
        },
        {
            "chamber": "House",
            "congress": 117,
            "jacketNumber": 48031,
            "updateDate": "2022-10-19 21:15:20+00:00",
            "url": "https://api.congress.gov/v3/committee-print/117/house/48031?format=json"
        }
    ]
}
```

**Path Parameters**:

| Name | Description |
|------|-------------|
| `congress` * | integer (path) - The congress number. For example, the value can be 117. |

**Query Parameters**:

| Name | Description |
|------|-------------|
| `format` | string (query) - The data format. Value can be xml or json. |
| `offset` | integer (query) - The starting record returned. 0 is the first record. |
| `limit` | integer (query) - The number of records returned. The maximum limit is 250. |
| `fromDateTime` | string (query) - The starting timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |
| `toDateTime` | string (query) - The ending timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |

---

### **GET `/committee-print/{congress}/{chamber}`**

**Description**: Returns a list of committee prints filtered by the specified congress and chamber.

**Example Request**:

```
https://api.congress.gov/v3/committee-print/117/house?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "committeePrints": [
        {
            "chamber": "House",
            "congress": 117,
            "jacketNumber": 48144,
            "updateDate": "2022-08-01 21:19:33+00:00",
            "url": "https://api.congress.gov/v3/committee-print/117/house/48144?format=json"
        },
        {
            "chamber": "House",
            "congress": 117,
            "jacketNumber": 48031,
            "updateDate": "2022-10-19 21:15:20+00:00",
            "url": "https://api.congress.gov/v3/committee-print/117/house/48031?format=json"
        }
    ]
}
```

**Path Parameters**:

| Name | Description |
|------|-------------|
| `congress` * | integer (path) - The congress number. For example, the value can be 117. |
| `chamber` * | string (path) - The chamber name. Value can be house, senate, or nochamber. |

**Query Parameters**:

| Name | Description |
|------|-------------|
| `format` | string (query) - The data format. Value can be xml or json. |
| `offset` | integer (query) - The starting record returned. 0 is the first record. |
| `limit` | integer (query) - The number of records returned. The maximum limit is 250. |
| `fromDateTime` | string (query) - The starting timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |
| `toDateTime` | string (query) - The ending timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |

---

### **GET `/committee-print/{congress}/{chamber}/{jacketNumber}`**

**Description**: Returns detailed information for a specified committee print.

**Example Request**:

```
https://api.congress.gov/v3/committee-print/117/house/48144?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "committeePrint": [
        {
            "associatedBills": [
                {
                    "congress": 117,
                    "number": "5768",
                    "type": "HR",
                    "url": "https://api.congress.gov/v3/bill/117/hr/5768?format=json"
                }
            ],
            "chamber": "House",
            "citation": "117-62",
            "committees": [
                {
                    "name": "Rules Committee",
                    "systemCode": "hsru00",
                    "url": "https://api.congress.gov/v3/committee/house/hsru00?format=json"
                }
            ],
            "congress": 117,
            "jacketNumber": 48144,
            "number": "62",
            "text": {
                "count": 4,
                "url": "https://api.congress.gov/v3/committee-print/117/house/48144/text?format=json"
            },
            "title": "RULES COMMITTEE PRINT 117-62 TEXT OF H.R. 5768, VIOLENT INCIDENT CLEAR- ANCE AND TECHNOLOGICAL INVESTIGATIVE METHODS ACT OF 2022",
            "updateDate": "2022-08-01 21:19:33+00:00"
        }
    ]
}
```

**Path Parameters**:

| Name | Description |
|------|-------------|
| `congress` * | integer (path) - The congress number. For example, the value can be 117. |
| `chamber` * | string (path) - The chamber name. Value can be house, senate, or nochamber. |
| `jacketNumber` * | integer (path) - The jacket number for the print. For example, the value can be 48144. |

**Query Parameters**:

| Name | Description |
|------|-------------|
| `format` | string (query) - The data format. Value can be xml or json. |

---

### **GET `/committee-print/{congress}/{chamber}/{jacketNumber}/text`**

**Description**: Returns the list of texts for a specified committee print.

**Example Request**:

```
https://api.congress.gov/v3/committee-print/117/house/48144/text?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "text": [
        {
            "type": "Formatted Text",
            "url": "https://www.congress.gov/117/cprt/HPRT48144/CPRT-117HPRT48144.htm"
        },
        {
            "type": "PDF",
            "url": "https://www.congress.gov/117/cprt/HPRT48144/CPRT-117HPRT48144.pdf"
        },
        {
            "type": "Formatted XML",
            "url": "https://www.congress.gov/117/cprt/HPRT48144/CPRT-117HPRT48144.xml"
        },
        {
            "type": "Generated HTML",
            "url": "https://www.congress.gov/117/cprt/HPRT48144/CPRT-117HPRT48144_gen.htm"
        }
    ]
}
```

**Path Parameters**:

| Name | Description |
|------|-------------|
| `congress` * | integer (path) - The congress number. For example, the value can be 117. |
| `chamber` * | string (path) - The chamber name. Value can be house, senate, or nochamber. |
| `jacketNumber` * | integer (path) - The jacket number for the print. For example, the value can be 48144. |

**Query Parameters**:

| Name | Description |
|------|-------------|
| `format` | string (query) - The data format. Value can be xml or json. |
| `offset` | integer (query) - The starting record returned. 0 is the first record. |
| `limit` | integer (query) - The number of records returned. The maximum limit is 250. |

---

## **Committee Meeting API**

### **GET `/committee-meeting`**

**Description**: Returns a list of committee meetings sorted by date of latest update.

**Example Request**:

```
https://api.congress.gov/v3/committee-meeting?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "committeeMeetings": [
        {
            "chamber": "House",
            "committee": {
                "name": "Agriculture Committee",
                "systemCode": "hsag00",
                "url": "https://api.congress.gov/v3/committee/house/hsag00?format=json"
            },
            "congress": 119,
            "eventId": 115678,
            "meetingDate": "2025-05-28T10:00:00Z",
            "title": "Hearing: Review of USDA Farm Programs",
            "type": "HHRG",
            "updateDate": "2025-05-20T14:32:18Z",
            "url": "https://api.congress.gov/v3/committee-meeting/119/house/hsag00/115678?format=json"
        },
        {
            "chamber": "Senate",
            "committee": {
                "name": "Appropriations Committee",
                "systemCode": "ssap00",
                "url": "https://api.congress.gov/v3/committee/senate/ssap00?format=json"
            },
            "congress": 119,
            "eventId": 115680,
            "meetingDate": "2025-05-27T14:30:00Z",
            "title": "Markup: FY2026 Defense Appropriations Bill",
            "type": "SSMT",
            "updateDate": "2025-05-20T12:15:42Z",
            "url": "https://api.congress.gov/v3/committee-meeting/119/senate/ssap00/115680?format=json"
        }
    ]
}
```

**Query Parameters**:

| Name | Description |
|------|-------------|
| `format` | string (query) - The data format. Value can be xml or json. |
| `offset` | integer (query) - The starting record returned. 0 is the first record. |
| `limit` | integer (query) - The number of records returned. The maximum limit is 250. |
| `fromDateTime` | string (query) - The starting timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |
| `toDateTime` | string (query) - The ending timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |
| `scheduledFrom` | string (query) - Filter meetings scheduled on or after this date. Use format: YYYY-MM-DDT00:00:00Z. |
| `scheduledTo` | string (query) - Filter meetings scheduled on or before this date. Use format: YYYY-MM-DDT00:00:00Z. |
| `sort` | string (query) - Sort by update date or meeting date. Value can be updateDate+asc, updateDate+desc, meetingDate+asc, or meetingDate+desc. |

---

### **GET `/committee-meeting/{congress}`**

**Description**: Returns a list of committee meetings filtered by the specified congress.

**Example Request**:

```
https://api.congress.gov/v3/committee-meeting/119?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "committeeMeetings": [
        {
            "chamber": "House",
            "committee": {
                "name": "Agriculture Committee",
                "systemCode": "hsag00",
                "url": "https://api.congress.gov/v3/committee/house/hsag00?format=json"
            },
            "congress": 119,
            "eventId": 115678,
            "meetingDate": "2025-05-28T10:00:00Z",
            "title": "Hearing: Review of USDA Farm Programs",
            "type": "HHRG",
            "updateDate": "2025-05-20T14:32:18Z",
            "url": "https://api.congress.gov/v3/committee-meeting/119/house/hsag00/115678?format=json"
        }
    ]
}
```

**Path Parameters**:

| Name | Description |
|------|-------------|
| `congress` * | integer (path) - The congress number. For example, the value can be 119. |

**Query Parameters**: Same as for `/committee-meeting`.

---

### **GET `/committee-meeting/{congress}/{chamber}`**

**Description**: Returns a list of committee meetings filtered by the specified congress and chamber.

**Example Request**:

```
https://api.congress.gov/v3/committee-meeting/119/house?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "committeeMeetings": [
        {
            "chamber": "House",
            "committee": {
                "name": "Agriculture Committee",
                "systemCode": "hsag00",
                "url": "https://api.congress.gov/v3/committee/house/hsag00?format=json"
            },
            "congress": 119,
            "eventId": 115678,
            "meetingDate": "2025-05-28T10:00:00Z",
            "title": "Hearing: Review of USDA Farm Programs",
            "type": "HHRG",
            "updateDate": "2025-05-20T14:32:18Z",
            "url": "https://api.congress.gov/v3/committee-meeting/119/house/hsag00/115678?format=json"
        }
    ]
}
```

**Path Parameters**:

| Name | Description |
|------|-------------|
| `congress` * | integer (path) - The congress number. For example, the value can be 119. |
| `chamber` * | string (path) - The chamber name. Value can be house or senate. |

**Query Parameters**: Same as for `/committee-meeting`.

---

### **GET `/committee-meeting/{congress}/{chamber}/{committeeCode}`**

**Description**: Returns a list of committee meetings filtered by the specified congress, chamber, and committee code.

**Example Request**:

```
https://api.congress.gov/v3/committee-meeting/119/house/hsag00?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "committeeMeetings": [
        {
            "chamber": "House",
            "committee": {
                "name": "Agriculture Committee",
                "systemCode": "hsag00",
                "url": "https://api.congress.gov/v3/committee/house/hsag00?format=json"
            },
            "congress": 119,
            "eventId": 115678,
            "meetingDate": "2025-05-28T10:00:00Z",
            "title": "Hearing: Review of USDA Farm Programs",
            "type": "HHRG",
            "updateDate": "2025-05-20T14:32:18Z",
            "url": "https://api.congress.gov/v3/committee-meeting/119/house/hsag00/115678?format=json"
        }
    ]
}
```

**Path Parameters**:

| Name | Description |
|------|-------------|
| `congress` * | integer (path) - The congress number. For example, the value can be 119. |
| `chamber` * | string (path) - The chamber name. Value can be house or senate. |
| `committeeCode` * | string (path) - The committee system code. For example, the value can be hsag00. |

**Query Parameters**: Same as for `/committee-meeting`.

---

### **GET `/committee-meeting/{congress}/{chamber}/{committeeCode}/{eventId}`**

**Description**: Returns detailed information for a specified committee meeting.

**Example Request**:

```
https://api.congress.gov/v3/committee-meeting/119/house/hsag00/115678?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "committeeMeeting": {
        "chamber": "House",
        "committee": {
            "name": "Agriculture Committee",
            "systemCode": "hsag00",
            "url": "https://api.congress.gov/v3/committee/house/hsag00?format=json"
        },
        "congress": 119,
        "eventId": 115678,
        "location": "1300 Longworth House Office Building",
        "meetingDate": "2025-05-28T10:00:00Z",
        "title": "Hearing: Review of USDA Farm Programs",
        "type": "HHRG",
        "updateDate": "2025-05-20T14:32:18Z",
        "witnesses": [
            {
                "firstName": "John",
                "lastName": "Smith",
                "organization": "Department of Agriculture",
                "position": "Secretary"
            },
            {
                "firstName": "Jane",
                "lastName": "Doe",
                "organization": "American Farm Bureau Federation",
                "position": "President"
            }
        ],
        "documents": [
            {
                "title": "Meeting Notice",
                "type": "NOTICE",
                "url": "https://docs.congress.gov/meetings/119/house/hsag00/115678/notice.pdf"
            },
            {
                "title": "Witness Testimony - John Smith",
                "type": "TESTIMONY",
                "url": "https://docs.congress.gov/meetings/119/house/hsag00/115678/testimony-smith.pdf"
            }
        ]
    }
}
```

**Path Parameters**:

| Name | Description |
|------|-------------|
| `congress` * | integer (path) - The congress number. For example, the value can be 119. |
| `chamber` * | string (path) - The chamber name. Value can be house or senate. |
| `committeeCode` * | string (path) - The committee system code. For example, the value can be hsag00. |
| `eventId` * | integer (path) - The event ID for the meeting. For example, the value can be 115678. |

**Query Parameters**:

| Name | Description |
|------|-------------|
| `format` | string (query) - The data format. Value can be xml or json. |

---
## **Hearings API**

### **GET `/hearing`**

**Description**: Returns a list of hearings sorted by date of latest update.

**Example Request**:

```
https://api.congress.gov/v3/hearing?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "hearings": [
        {
            "chamber": "House",
            "congress": 116,
            "jacketNumber": 41444,
            "updateDate": "2022-06-30 03:50:43+00:00",
            "url": "https://api.congress.gov/v3/hearing/117/house/41444?format=json"
        },
        {
            "chamber": "House",
            "congress": 116,
            "jacketNumber": 41365,
            "updateDate": "2022-06-30 03:50:43+00:00",
            "url": "https://api.congress.gov/v3/hearing/117/house/41365?format=json"
        }
    ]
}
```

**Query Parameters**:

| Name | Description |
|------|-------------|
| `format` | string (query) - The data format. Value can be xml or json. |
| `offset` | integer (query) - The starting record returned. 0 is the first record. |
| `limit` | integer (query) - The number of records returned. The maximum limit is 250. |

---

### **GET `/hearing/{congress}`**

**Description**: Returns a list of hearings filtered by the specified congress.

**Example Request**:

```
https://api.congress.gov/v3/hearing/116?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "hearings": [
        {
            "chamber": "House",
            "congress": 116,
            "jacketNumber": 41444,
            "updateDate": "2022-06-30 03:50:43+00:00",
            "url": "https://api.congress.gov/v3/hearing/117/house/41444?format=json"
        },
        {
            "chamber": "House",
            "congress": 116,
            "jacketNumber": 41365,
            "updateDate": "2022-06-30 03:50:43+00:00",
            "url": "https://api.congress.gov/v3/hearing/117/house/41365?format=json"
        }
    ]
}
```

**Path Parameters**:

| Name | Description |
|------|-------------|
| `congress` * | integer (path) - The congress number. For example, the value can be 116. |

**Query Parameters**:

| Name | Description |
|------|-------------|
| `format` | string (query) - The data format. Value can be xml or json. |
| `offset` | integer (query) - The starting record returned. 0 is the first record. |
| `limit` | integer (query) - The number of records returned. The maximum limit is 250. |

---

### **GET `/hearing/{congress}/{chamber}`**

**Description**: Returns a list of hearings filtered by the specified congress and chamber.

**Example Request**:

```
https://api.congress.gov/v3/hearing/116/house?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "hearings": [
        {
            "chamber": "House",
            "congress": 116,
            "jacketNumber": 41444,
            "updateDate": "2022-06-30 03:50:43+00:00",
            "url": "https://api.congress.gov/v3/hearing/117/house/41444?format=json"
        },
        {
            "chamber": "House",
            "congress": 116,
            "jacketNumber": 41365,
            "updateDate": "2022-06-30 03:50:43+00:00",
            "url": "https://api.congress.gov/v3/hearing/117/house/41365?format=json"
        }
    ]
}
```

**Path Parameters**:

| Name | Description |
|------|-------------|
| `congress` * | integer (path) - The congress number. For example, the value can be 116. |
| `chamber` * | string (path) - The chamber name. Value can be house, senate, or nochamber. |

**Query Parameters**:

| Name | Description |
|------|-------------|
| `format` | string (query) - The data format. Value can be xml or json. |
| `offset` | integer (query) - The starting record returned. 0 is the first record. |
| `limit` | integer (query) - The number of records returned. The maximum limit is 250. |

---

### **GET `/hearing/{congress}/{chamber}/{jacketNumber}`**

**Description**: Returns detailed information for a specified hearing.

**Example Request**:

```
https://api.congress.gov/v3/hearing/116/house/41365?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "hearing": {
        "associatedMeeting": {
            "eventId": "110484",
            "url": "http://api.congress.gov/v3/committee-meeting/116/house/110484?format=xml"
        },
        "chamber": "House",
        "citation": "H.Hrg.116",
        "committees": [
            {
                "name": "House Agriculture Committee",
                "systemCode": "hsag00",
                "url": "https://api.congress.gov/v3/committee/house/hsag00?format=json"
            }
        ],
        "congress": 116,
        "dates": [
            {
                "date": "2020-02-11"
            }
        ],
        "formats": [
            {
                "type": "Formatted Text",
                "url": "https://www.congress.gov/116/chrg/CHRG-116hhrg41365/CHRG-116hhrg41365.htm"
            },
            {
                "type": "PDF",
                "url": "https://www.congress.gov/116/chrg/CHRG-116hhrg41365/CHRG-116hhrg41365.pdf"
            }
        ],
        "jacketNumber": 41365,
        "libraryOfCongressIdentifier": "LC65344",
        "title": "ECONOMIC OPPORTUNITIES FROM LOCAL AGRICULTURAL MARKETS",
        "updateDate": "2022-06-30 03:50:43+00:00"
    }
}
```

**Path Parameters**:

| Name | Description |
|------|-------------|
| `congress` * | integer (path) - The congress number. For example, the value can be 116. |
| `chamber` * | string (path) - The chamber name. Value can be house, senate, or nochamber. |
| `jacketNumber` * | integer (path) - The jacket number for the hearing. For example, the value can be 41365. |

**Query Parameters**:

| Name | Description |
|------|-------------|
| `format` | string (query) - The data format. Value can be xml or json. |
## **Congressional Record API**

### **GET `/congressional-record`**

**Description**: Returns a list of congressional record issues sorted by most recent.

**Example Request**:

```
https://api.congress.gov/v3/congressional-record/?y=2022&m=6&d=28&api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "Results": {
        "IndexStart": 1,
        "Issues": [
            {
                "Congress": "117",
                "Id": 26958,
                "Issue": "109",
                "Links": {
                    "Digest": {
                        "Label": "Daily Digest",
                        "Ordinal": 1,
                        "PDF": [
                            {
                                "Part": "1",
                                "Url": "https://www.congress.gov/117/crec/2022/06/28/168/109/CREC-2022-06-28-dailydigest.pdf"
                            }
                        ]
                    },
                    "FullRecord": {
                        "Label": "Entire Issue",
                        "Ordinal": 5,
                        "PDF": [
                            {
                                "Part": "1",
                                "Url": "https://www.congress.gov/117/crec/2022/06/28/168/109/CREC-2022-06-28.pdf"
                            }
                        ]
                    },
                    "House": {
                        "Label": "House Section",
                        "Ordinal": 3,
                        "PDF": [
                            {
                                "Part": "1",
                                "Url": "https://www.congress.gov/117/crec/2022/06/28/168/109/CREC-2022-06-28-house.pdf"
                            }
                        ]
                    },
                    "Remarks": {
                        "Label": "Extensions of Remarks Section",
                        "Ordinal": 4,
                        "PDF": [
                            {
                                "Part": "1",
                                "Url": "https://www.congress.gov/117/crec/2022/06/28/168/109/CREC-2022-06-28-extensions.pdf"
                            }
                        ]
                    },
                    "Senate": {
                        "Label": "Senate Section",
                        "Ordinal": 2,
                        "PDF": [
                            {
                                "Part": "1",
                                "Url": "https://www.congress.gov/117/crec/2022/06/28/168/109/CREC-2022-06-28-senate.pdf"
                            }
                        ]
                    }
                },
                "PublishDate": "2022-06-28",
                "Session": "2",
                "Volume": "168"
            }
        ]
    }
}```

**Query Parameters**:

| Name | Description |
|------|-------------|
| `format` | string (query) - The data format. Value can be xml or json. |
| `y` | integer (query) - The year the issue was published. For example, the value can be 2022. |
| `m` | integer (query) - The month the issue was published. For example, the value can be 6. |
| `d` | integer (query) - The day the issue was published. For example, the value can be 28. |
| `offset` | integer (query) - The starting record returned. 0 is the first record. |
| `limit` | integer (query) - The number of records returned. The maximum limit is 250. |

## **Daily Congressional Record API**

### **GET `/daily-congressional-record`**

**Description**: Returns a list of daily congressional record issues sorted by most recent.

**Example Request**:

```
https://api.congress.gov/v3/daily-congressional-record?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "dailyCongressionalRecord": [
        {
            "congress": "118",
            "issueDate": "2023-07-11T04:00:00Z",
            "issueNumber": "118",
            "sessionNumber": "1",
            "updateDate": "2023-07-12T11:30:30Z",
            "url": "http://api.congress.gov/v3/daily-congressional-record/169/118?format=json",
            "volumeNumber": "169"
        },
        {
            "congress": "118",
            "issueDate": "2023-07-07T04:00:00Z",
            "issueNumber": "117",
            "sessionNumber": "1",
            "updateDate": "2023-07-12T11:00:30Z",
            "url": "http://api.congress.gov/v3/daily-congressional-record/169/117?format=json",
            "volumeNumber": "169"
        },
        {
            "congress": "118",
            "issueDate": "2023-07-06T04:00:00Z",
            "issueNumber": "116",
            "sessionNumber": "1",
            "updateDate": "2023-07-07T21:03:48Z",
            "url": "http://api.congress.gov/v3/daily-congressional-record/169/116?format=json",
            "volumeNumber": "169"
        }
    ]
}```

**Query Parameters**:

| Name | Description |
|------|-------------|
| `format` | string (query) - The data format. Value can be xml or json. |
| `offset` | integer (query) - The starting record returned. 0 is the first record. |
| `limit` | integer (query) - The number of records returned. The maximum limit is 250. |

### **GET `/daily-congressional-record/{volumeNumber}`**

**Description**: Returns a list of daily Congressional Records filtered by the specified volume number.

**Example Request**:

```
https://api.congress.gov/v3/daily-congressional-record/166?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "dailyCongressionalRecord": [
        {
            "congress": "116",
            "issueDate": "2021-01-03T05:00:00Z",
            "issueNumber": "225",
            "sessionNumber": "2",
            "updateDate": "2021-01-04T11:15:10Z",
            "url": "http://api.congress.gov/v3/daily-congressional-record/166/225?format=json",
            "volumeNumber": "166"
        },
        {
            "congress": "116",
            "issueDate": "2021-01-01T05:00:00Z",
            "issueNumber": "224",
            "sessionNumber": "2",
            "updateDate": "2021-01-03T15:45:11Z",
            "url": "http://api.congress.gov/v3/daily-congressional-record/166/224?format=json",
            "volumeNumber": "166"
        }
    ]
}```

**Parameters**:

| Name | Description |
|------|-------------|
| `format` | string (query) - The data format. Value can be xml or json. |
| `offset` | integer (query) - The starting record returned. 0 is the first record. |
| `limit` | integer (query) - The number of records returned. The maximum limit is 250. |
| `volumeNumber` * | string (path) - The specified volume of the daily Congressional record, for example 166. |

### **GET `/daily-congressional-record/{volumeNumber}/{issueNumber}`**

**Description**: Returns a list of daily Congressional Records filtered by the specified volume number and specified issue number.

**Example Request**:

```
https://api.congress.gov/v3/daily-congressional-record/168/153?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "issue": [
        {
            "congress": "117",
            "fullIssue": "2021-01-03T05:00:00Z",
            "articles": {
                "count": 256,
                "url": "http://api.congress.gov/v3/daily-congressional-record/168/153/articles?format=json"
            },
            "entireIssue": [
                {
                    "part": "1",
                    "type": "Formatted Text",
                    "url": "https://congress.gov/117/crec/2022/09/22/168/153/CREC-2022-09-22-pt1-PgD1015.htm"
                },
                {
                    "part": "1",
                    "type": "PDF",
                    "url": "https://congress.gov/117/crec/2022/09/22/168/153/CREC-2022-09-22.pdf"
                }
            ],
            "sections": [
                {
                    "endPage": "D1020",
                    "name": "Daily Digest",
                    "startPage": "D1015",
                    "text": [
                        {
                            "type": "PDF",
                            "url": "https://congress.gov/117/crec/2022/09/22/168/153/CREC-2022-09-22-dailydigest.pdf"
                        },
                        {
                            "type": "Formatted Text",
                            "url": "https://congress.gov/117/crec/2022/09/22d22se2-1.htm"
                        }
                    ]
                },
                {
                    "endPage": "E976",
                    "name": "Extension of Remarks Section",
                    "startPage": "E965",
                    "text": [
                        {
                            "part": "1",
                            "type": "PDF",
                            "url": "https://congress.gov/117/crec/2022/09/22/168/153/CREC-2022-09-22-extensions.pdf"
                        }
                    ]
                },
                {
                    "endPage": "E976",
                    "name": "House Section",
                    "startPage": "H8069",
                    "text": [
                        {
                            "part": "1",
                            "type": "PDF",
                            "url": "https://congress.gov/117/crec/2022/09/22/168/153/CREC-2022-09-22-house.pdf"
                        }
                    ]
                },
                {
                    "endPage": "E976",
                    "name": "Senate Section",
                    "startPage": "S4941",
                    "text": [
                        {
                            "part": "1",
                            "type": "PDF",
                            "url": "https://congress.gov/117/crec/2022/09/22/168/153/CREC-2022-09-22-senate.pdf"
                        }
                    ]
                }
            ]
        }
    ],
    "issueDate": "2022-09-22T04:00:00Z",
    "issueNumber": "153",
    "sessionNumber": 2,
    "updateDate": "2022-09-23T12:00:14Z",
    "url": "http://api.congress.gov/v3/daily-congressional-record/168/153?format=json",
    "volumeNumber": 168,
    "request": {
        "contentType": "application/json",
        "format": "json",
        "issueNumber": "153",
        "volumeNumber": "168"
    }
}```

**Parameters**:

| Name | Description |
|------|-------------|
| `format` | string (query) - The data format. Value can be xml or json. |
| `offset` | integer (query) - The starting record returned. 0 is the first record. |
| `limit` | integer (query) - The number of records returned. The maximum limit is 250. |
| `volumeNumber` * | string (path) - The specified volume of the daily Congressional record, for example 166. |
| `issueNumber` * | string (path) - The specified issue of the daily Congressional record, for example 153. |

### **GET `/daily-congressional-record/{volumeNumber}/{issueNumber}/articles`**

**Description**: Returns a list of daily Congressional Record articles filtered by the specified volume number and specified issue number.

**Example Request**:

```
https://api.congress.gov/v3/daily-congressional-record/167/21/articles?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "articles": [
        {
            "name": "Daily Digest",
            "sectionArticles": [
                {
                    "endPage": "D94",
                    "startPage": "D93",
                    "text": [
                        {
                            "type": "Formatted Text",
                            "url": "https://congress.gov/117/crec/2021/02/04/167/21/modified/CREC-2021-02-04-pt1-PgD93-3.htm"
                        },
                        {
                            "type": "PDF",
                            "url": "https://congress.gov/117/crec/2021/02/04/167/21/CREC-2021-02-04-pt1-PgD93-3.pdf"
                        },
                        {
                            "type": "Formatted Text",
                            "url": "https://congress.gov/117/crec/2021/02/04/modified/CREC-2021-02-04-pt2-PgD93-3.htm"
                        },
                        {
                            "type": "PDF",
                            "url": "https://congress.gov/117/crec/2021/02/04/CREC-2021-02-04-pt2-PgD93-3.pdf"
                        }
                    ],
                    "title": "Daily Digest/Next Meeting of the SENATE + Next Meeting of the HOUSE OF REPRESENTATIVES + Other End Matter; Congressional Record Vol. 167, No. 21"
                }
            ]
        }
    ]
}```

**Parameters**:

| Name | Description |
|------|-------------|
| `format` | string (query) - The data format. Value can be xml or json. |
| `offset` | integer (query) - The starting record returned. 0 is the first record. |
| `limit` | integer (query) - The number of records returned. The maximum limit is 250. |
| `volumeNumber` * | string (path) - The specified volume of the daily Congressional record, for example 166. |
| `issueNumber` * | string (path) - The specified issue of the daily Congressional record, for example 153. |
---

# **Bound Congressional Record API Documentation**

## **Overview**

The Bound Congressional Record API provides access to bound Congressional Record data from the Congress.gov API.

Base URL: `https://api.congress.gov/v3/bound-congressional-record`

All endpoints require an API key provided via `?api_key=[INSERT_KEY]`.

---

## **Endpoints**

### **GET `/bound-congressional-record`**

**Description**: Returns a list of bound Congressional Records sorted by most recent.

**Example Request**:

```
https://api.congress.gov/v3/bound-congressional-record?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
  "boundCongressionalRecord": [
          {
          "congress": "109",
          "date": "2005-06-20",
          "sessionNumber": "1",
          "updateDate": "2020-04-08",
          "url": "http://api.congress.gov/v3/bound-congressional-record/2005/6/20?format=json",
          "volumeNumber": "151"
          },
          {
          "congress": "106",
          "date": "1999-07-01",
          "sessionNumber": "1",
          "updateDate": "2020-04-08",
          "url": "http://api.congress.gov/v3/bound-congressional-record/1999/7/1?format=json",
          "volumeNumber": "145"
           }
  ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| `format` | string (query) - The data format. Value can be xml or json. |
| `offset` | integer (query) - The starting record returned. 0 is the first record. |
| `limit` | integer (query) - The number of records returned. The maximum limit is 250. |

---

### **GET `/bound-congressional-record/{year}`**

**Description**: Returns a list of bound Congressional Records filtered by the specified year.

**Example Request**:

```
https://api.congress.gov/v3/bound-congressional-record/1990?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "boundCongressionalRecord": [
        {
            "congress": "101",
            "date": "1990-02-28",
            "sessionNumber": "2",
            "updateDate": "2020-10-20",
            "url": "http://api.congress.gov/v3/bound-congressional-record/1990/2/28?format=json",
            "volumeNumber": "136"
        },
        {
            "congress": "101",
            "issueDate": "1990-03-19",
            "sessionNumber": "2",
            "updateDate": "2020-10-20",
            "url": "http://api.congress.gov/v3/bound-congressional-record/1990/3/19?format=json",
            "volumeNumber": "136"
        }
    ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| `format` | string (query) - The data format. Value can be xml or json. |
| `offset` | integer (query) - The starting record returned. 0 is the first record. |
| `limit` | integer (query) - The number of records returned. The maximum limit is 250. |
| `year` * | string (path) - The specified year of the bound Congressional record, for example 1990. |

---

### **GET `/bound-congressional-record/{year}/{month}`**

**Description**: Returns a list of bound Congressional Records filtered by the specified year and specified month.

**Example Request**:

```
https://api.congress.gov/v3/bound-congressional-record/1990/5?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
   "boundCongressionalRecord": [
       {
           "congress": 101,
            "date": "1990-05-01",
            "sessionNumber": 2,
            "updateDate": "2020-10-20",
            "url": "http://api.congress.gov/v3/bound-congressional-record/1990/5/1?format=json",
            "volumeNumber": 136
        },
        {
           "congress": 101,
           "date": "1990-05-01",
           "sessionNumber": 2,
           "updateDate": "2020-10-20",
           "url": "http://api.congress.gov/v3/bound-congressional-record/1990/5/1?format=json",
            "volumeNumber": 136
        }
   ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| `format` | string (query) - The data format. Value can be xml or json. |
| `offset` | integer (query) - The starting record returned. 0 is the first record. |
| `limit` | integer (query) - The number of records returned. The maximum limit is 250. |
| `year` * | string (path) - The specified year of the bound Congressional record, for example 1990. |
| `month` * | string (path) - The specified month of the bound Congressional record, for example 4 for April. |

---

### **GET `/bound-congressional-record/{year}/{month}/{day}`**

**Description**: Returns a list of bound Congressional Records filtered by the specified year, specified month and specified day.

**Example Request**:

```
https://api.congress.gov/v3/bound-congressional-record/1948/05/19?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
   "boundCongressionalRecord": [
       {
          "congress": 80,
          "date": "1948-05-19",
          "sections": [
              {
              "endPage": 6155,
              "name": "House of Representatives",
              "startPage": 6099
              }
          ],
          "sessionNumber": 2,
          "updateDate": "2023-04-27",
          "volumeNumber": 94
        },
        {
          "congress": 80,
          "date": "1948-05-19",
          "sections": [
              {
              "endPage": 6098,
              "name": "Senate",
              "startPage": 6051
              }
          ],
          "sessionNumber": 2,
          "updateDate": "2023-04-27",
          "volumeNumber": 94
        },
        {
          "congress": 80,
          "date": "1948-05-19",
          "sections": [
              {
              "endPage": 6155,
              "name": "Entire Issue",
              "startPage": 6051
              }
          ],
          "sessionNumber": 2,
          "updateDate": "2023-04-27",
          "volumeNumber": 94
        },
        {
          "congress": 80,
          "dailyDigest": {
                    "endPage": 365,
                    "startPage": 362,
                    "text": [
                        {
                            "type": "PDF",
                            "url": "http://congress.gov/crecb/1948/GPO-CRECB-1948-pt14-Pages362-365.pdf"
                        }
                    ]
            },
            "date": "1948-05-19",
            "sections": [
                {
                    "endPage": 365,
                    "name": "Daily Digest",
                    "startPage": 362
                }
            ],
            "sessionNumber": 2,
            "updateDate": "2022-11-04",
            "volumeNumber": 94
        }
   ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| `format` | string (query) - The data format. Value can be xml or json. |
| `offset` | integer (query) - The starting record returned. 0 is the first record. |
| `limit` | integer (query) - The number of records returned. The maximum limit is 250. |
| `year` * | string (path) - The specified year of the bound Congressional record, for example 1990. |
| `month` * | string (path) - The specified month of the bound Congressional record, for example 4 for April. |
| `day` * | string (path) - The specified day of the bound Congressional record, for example 18. |
---

# **House Communication API Documentation**

## **Overview**

The House Communication API provides access to House communication data from the Congress.gov API.

Base URL: `https://api.congress.gov/v3/house-communication`

All endpoints require an API key provided via `?api_key=[INSERT_KEY]`.

---

## **Endpoints**

### **GET `/house-communication`**

**Description**: Returns a list of House communications.

**Example Request**:

```
https://api.congress.gov/v3/house-communication?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "houseCommunications": [
        {
            "chamber": "House",
            "communicationNumber": 2057,
            "communicationType": {
                "code": "EC",
                "name": "Executive Communication"
            },
            "congressNumber": 117,
            "url": "https://api.congress.gov/v3/house-communication/117/ec/2057?format=json"
        },
        {
            "chamber": "House",
            "communicationNumber": 125,
            "communicationType": {
                "code": "EC",
                "name": "Executive Communication"
            },
            "congressNumber": 115,
            "url": "https://api.congress.gov/v3/house-communication/115/ec/125?format=json"
        }
    ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| `format` | string (query) - The data format. Value can be xml or json. |
| `offset` | integer (query) - The starting record returned. 0 is the first record. |
| `limit` | integer (query) - The number of records returned. The maximum limit is 250. |

---

### **GET `/house-communication/{congress}`**

**Description**: Returns a list of House communications filtered by the specified congress.

**Example Request**:

```
https://api.congress.gov/v3/house-communication/117?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "houseCommunications": [
        {
            "chamber": "House",
            "communicationType": {
                "code": "EC",
                "name": "Executive Communication"
            },
            "congressNumber": 117,
            "number": "2057",
            "reportNature": "A letter reporting violations of the Antideficiency Act, by the United States Coast Guard.",
            "submittingAgency": "Department of Homeland Security",
            "submittingOfficial": "Secretary",
            "updateDate": "2021-09-01",
            "url": "https://api.congress.gov/v3/house-communication/117/ec/2057?format=json"
        },
        {
            "chamber": "House",
            "communicationType": {
                "code": "EC",
                "name": "Executive Communication"
            },
            "congressNumber": 117,
            "legalAuthority": "Public Law 93\u2013198, section 602(c)(1); (87 Stat. 814)",
            "number": "3089",
            "reportNature": "D.C. Act 24-267, \"Jamal Khashoggi Way Designation Way Act of 2021\".",
            "submittingAgency": "Council of the District of Columbia",
            "submittingOfficial": "Chairman",
            "updateDate": "2022-01-12",
            "url": "https://api.congress.gov/v3/house-communication/117/ec/3089?format=json"
        }
    ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| `format` | string (query) - The data format. Value can be xml or json. |
| `offset` | integer (query) - The starting record returned. 0 is the first record. |
| `limit` | integer (query) - The number of records returned. The maximum limit is 250. |
| `congress` * | integer (path) - The congress number. For example, the value can be 117. |

---

### **GET `/house-communication/{congress}/{communicationType}`**

**Description**: Returns a list of House communications filtered by the specified congress and communication type.

**Example Request**:

```
https://api.congress.gov/v3/house-communication/117/ec?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "houseCommunications": [
        {
            "chamber": "House",
            "communicationType": {
                "code": "EC",
                "name": "Executive Communication"
            },
            "congressNumber": 117,
            "number": "2057",
            "reportNature": "A letter reporting violations of the Antideficiency Act, by the United States Coast Guard.",
            "submittingAgency": "Department of Homeland Security",
            "submittingOfficial": "Secretary",
            "updateDate": "2021-09-01",
            "url": "https://api.congress.gov/v3/house-communication/117/ec/2057?format=json"
        },
        {
            "chamber": "House",
            "communicationNumber": 3089,
            "communicationType": {
                "code": "EC",
                "name": "Executive Communication"
            },
            "congressNumber": 117,
            "legalAuthority": "Public Law 93\u2013198, section 602(c)(1); (87 Stat. 814)",
            "number": "3089",
            "reportNature": "D.C. Act 24-267, \"Jamal Khashoggi Way Designation Way Act of 2021\".",
            "submittingAgency": "Council of the District of Columbia",
            "submittingOfficial": "Chairman",
            "updateDate": "2022-01-12",
            "url": "https://api.congress.gov/v3/house-communication/117/ec/3089?format=json"
        }
    ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| `format` | string (query) - The data format. Value can be xml or json. |
| `offset` | integer (query) - The starting record returned. 0 is the first record. |
| `limit` | integer (query) - The number of records returned. The maximum limit is 250. |
| `congress` * | integer (path) - The congress number. For example, the value can be 117. |
| `communicationType` * | string (path) - The type of communication. Value can be ec, ml, pm, or pt. |

---

### **GET `/house-communication/{congress}/{communicationType}/{communicationNumber}`**

**Description**: Returns detailed information for a specified House communication.

**Example Request**:

```
https://api.congress.gov/v3/house-communication/117/ec/3324?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "house-communication": {
        "abstract": "A letter from the Chairman, Council of the District of Columbia, transmitting DC Act 24-299, \"Closing of a Portion of a Public Alley in Square 5138, S.O. 20-07517, Act of 2021\", pursuant to Public Law 93\u2013198, section 602(c)(1); (87 Stat. 814); to the Committee on Oversight and Reform.",
        "chamber": "House",
        "committees": [
            {
                "name": "Oversight and Accountability Committee",
                "referralDate": "2022-02-01",
                "systemCode": "hsgo00",
                "url": "api.congress.gov/v3/committee/house/hsgo00"
            }
        ],
        "communicationType": {
            "code": "EC",
            "name": "Executive Communication"
        },
        "congressNumber": 117,
        "congressionalRecordDate": "2022-02-01",
        "isRulemaking": "False",
        "legalAuthority": "Public Law 93\u2013198, section 602(c)(1); (87 Stat. 814)",
        "matchingRequirements": [
            {
                "number": "2120",
                "url": "http://api.congress.gov/v3/house-requirement/2120"
            }
        ],
        "number": "3324",
        "reportNature": "DC Act 24-299, \"Closing of a Portion of a Public Alley in Square 5138, S.O. 20-07517, Act of 2021\".",
        "sessionNumber": 2,
        "submittingAgency": "Council of the District of Columbia",
        "submittingOfficial": "Chairman",
        "updateDate": "2022-02-02"
    }
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| `format` | string (query) - The data format. Value can be xml or json. |
| `congress` * | integer (path) - The congress number. For example, the value can be 117. |
| `communicationType` * | string (path) - The type of communication. Value can be ec, ml, pm, or pt. |
| `communicationNumber` * | integer (path) - The communication's assigned number. For example, the value can be 3324. |
---

# **House Requirements API Documentation**

## **Overview**

The House Requirements API provides access to House requirement data from the Congress.gov API.

Base URL: `https://api.congress.gov/v3/house-requirement`

All endpoints require an API key provided via `?api_key=[INSERT_KEY]`.

---

## **Endpoints**

### **GET `/house-requirement`**

**Description**: Returns a list of House requirements.

**Example Request**:

```
https://api.congress.gov/v3/house-requirement?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "houseRequirements": [
        {
            "number": 8070,
            "updateDate": "2021-08-13",
            "url": "https://api.congress.gov/v3/house-requirement/8070?format=json"
        },
        {
            "number": 6463,
            "updateDate": "2021-08-13",
            "url": "https://api.congress.gov/v3/house-requirement/6463?format=json"
        }
    ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| `format` | string (query) - The data format. Value can be xml or json. |
| `offset` | integer (query) - The starting record returned. 0 is the first record. |
| `limit` | integer (query) - The number of records returned. The maximum limit is 250. |

---

### **GET `/house-requirement/{requirementNumber}`**

**Description**: Returns detailed information for a specified House requirement.

**Example Request**:

```
https://api.congress.gov/v3/house-requirement/8070?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "houseRequirement": {
        "activeRecord": true,
        "frequency": "[No deadline specified].",
        "legalAuthority": "5 U.S.C. 801(a)(1)(A); Public Law 104\u2013121, section 251; (110 Stat. 868)",
        "matchingCommunications": {
            "count": 85085,
            "url": "https://api.congress.gov/v3/house-requirement/8070/matching-communications?format=json"
        },
        "nature": "Congressional review of agency rulemaking.",
        "number": 8070,
        "parentAgency": "Multiple Executive Agencies and Departments",
        "submittingAgency": "Multiple Executive Agencies and Departments",
        "submittingOfficial": null,
        "updateDate": "2021-08-13"
    }
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| `format` | string (query) - The data format. Value can be xml or json. |
| `requirementNumber` * | integer (path) - The requirement's assigned number. For example, the value can be 8070. |

---

### **GET `/house-requirement/{requirementNumber}/matching-communications`**

**Description**: Returns a list of matching communications to a House requirement.

**Example Request**:

```
https://api.congress.gov/v3/house-requirement/8070/matching-communications?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "matchingCommunications": [
        {
            "chamber": "House",
            "communicationType": {
                "code": "EC",
                "name": "Executive Communication"
            },
            "congress": 112,
            "number": 2,
            "url": "https://api.congress.gov/v3/house-communication/112/EC/2?format=json"
        },
        {
            "chamber": "House",
            "communicationType": {
                "code": "EC",
                "name": "Executive Communication"
            },
            "congress": 112,
            "number": 3,
            "url": "https://api.congress.gov/v3/house-communication/112/EC/3?format=json"
        }
    ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| `format` | string (query) - The data format. Value can be xml or json. |
| `offset` | integer (query) - The starting record returned. 0 is the first record. |
| `limit` | integer (query) - The number of records returned. The maximum limit is 250. |
| `requirementNumber` * | integer (path) - The requirement's assigned number. For example, the value can be 8070. |
---

# **Senate Communication API Documentation**

## **Overview**

The Senate Communication API provides access to Senate communication data from the Congress.gov API.

Base URL: `https://api.congress.gov/v3/senate-communication`

All endpoints require an API key provided via `?api_key=[INSERT_KEY]`.

---

## **Endpoints**

### **GET `/senate-communication`**

**Description**: Returns a list of Senate communications.

**Example Request**:

```
https://api.congress.gov/v3/senate-communication?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "senateCommunications": [
        {
            "chamber": "Senate",
            "communicationType": {
                "code": "EC",
                "name": "Executive Communication"
            },
            "congress": 117,
            "number": 1615,
            "updateDate": "2021-08-16 20:24:19+00:00",
            "url": "https://api.congress.gov/v3/senate-communication/117/ec/1615?format=json"
        },
        {
            "chamber": "Senate",
            "communicationType": {
                "code": "EC",
                "name": "Executive Communication"
            },
            "congress": 117,
            "number": 2040,
            "updateDate": "2021-09-23 07:15:14+00:00",
            "url": "https://api.congress.gov/v3/senate-communication/117/ec/2040?format=json"
        }
    ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| `format` | string (query) - The data format. Value can be xml or json. |
| `offset` | integer (query) - The starting record returned. 0 is the first record. |
| `limit` | integer (query) - The number of records returned. The maximum limit is 250. |

---

### **GET `/senate-communication/{congress}`**

**Description**: Returns a list of Senate communications filtered by the specified congress.

**Example Request**:

```
https://api.congress.gov/v3/senate-communication/117?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "senateCommunications": [
        {
            "chamber": "Senate",
            "communicationType": {
                "code": "EC",
                "name": "Executive Communication"
            },
            "congress": 117,
            "number": 1615,
            "updateDate": "2021-08-16T20:24:19Z",
            "url": "https://api.congress.gov/v3/senate-communication/117/ec/1615?format=json"
        },
        {
            "chamber": "Senate",
            "communicationType": {
                "code": "EC",
                "name": "Executive Communication"
            },
            "congress": 117,
            "number": 2040,
            "updateDate": "2021-09-23T07:15:14Z",
            "url": "https://api.congress.gov/v3/senate-communication/117/ec/2040?format=json"
        }
    ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| `format` | string (query) - The data format. Value can be xml or json. |
| `offset` | integer (query) - The starting record returned. 0 is the first record. |
| `limit` | integer (query) - The number of records returned. The maximum limit is 250. |
| `congress` * | integer (path) - The congress number. For example, the value can be 117. |

---

### **GET `/senate-communication/{congress}/{communicationType}`**

**Description**: Returns a list of Senate communications filtered by the specified congress and communication type.

**Example Request**:

```
https://api.congress.gov/v3/senate-communication/117/ec?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "senateCommunications": [
        {
            "chamber": "Senate",
            "communicationType": {
                "code": "EC",
                "name": "Executive Communication"
            },
            "congress": 117,
            "number": 1615,
            "updateDate": "2021-08-16 20:24:19+00:00",
            "url": "https://api.congress.gov/v3/senate-communication/117/ec/1615?format=json"
        },
        {
            "chamber": "Senate",
            "communicationType": {
                "code": "EC",
                "name": "Executive Communication"
            },
            "congress": 117,
            "number": 2040,
            "updateDate": "2021-09-23T07:15:14:00Z",
            "url": "https://api.congress.gov/v3/senate-communication/117/ec/2040?format=json"
        }
    ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| `format` | string (query) - The data format. Value can be xml or json. |
| `offset` | integer (query) - The starting record returned. 0 is the first record. |
| `limit` | integer (query) - The number of records returned. The maximum limit is 250. |
| `congress` * | integer (path) - The congress number. For example, the value can be 117. |
| `communicationType` * | string (path) - The type of communication. Value can be ec, pm, or pom. |

---

### **GET `/senate-communication/{congress}/{communicationType}/{communicationNumber}`**

**Description**: Returns detailed information for a specified Senate communication.

**Example Request**:

```
https://api.congress.gov/v3/senate-communication/117/ec/2561?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "senateCommunication": {
        "abstract": "A communication from the Board Chairman and Chief Executive Officer, Farm Credit Administration, transmitting, pursuant to law, the Administration's annual report for calendar year 2021; to the Committee on Agriculture, Nutrition, and Forestry.",
        "chamber": "Senate",
        "committees": [
            {
                "name": "Agriculture, Nutrition, and Forestry Committee",
                "referralDate": "2021-11-03",
                "systemCode": "ssaf00",
                "url": "https://api.congress.gov/v3/committee/senate/ssaf00"
            }
        ],
        "communicationType": {
            "code": "EC",
            "name": "Executive Communication"
        },
        "congress": 117,
        "congressionalRecordDate": "2021-11-03",
        "number": 2561,
        "sessionNumber": 1,
        "updateDate": "2021-11-04T07:15:16Z"
    }
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| `format` | string (query) - The data format. Value can be xml or json. |
| `congress` * | integer (path) - The congress number. For example, the value can be 117. |
| `communicationType` * | string (path) - The type of communication. Value can be ec, pm, or pom. |
| `communicationNumber` * | integer (path) - The communication's assigned number. For example, the value can be 2561. |
---

# **Nominations API Documentation**

## **Overview**

The Nominations API provides access to nomination data from the Congress.gov API.

Base URL: `https://api.congress.gov/v3/nomination`

All endpoints require an API key provided via `?api_key=[INSERT_KEY]`.

---

## **Endpoints**

### **GET `/nomination`**

**Description**: Returns a list of nominations sorted by date received from the President.

**Example Request**:

```
https://api.congress.gov/v3/nomination?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "nominations": [
        {
            "citation": "PN2804",
            "congress": 117,
            "latestAction": {
                "actionDate": "2022-12-07",
                "text": "Received in the Senate and referred to the Committee on Armed Services."
            },
            "nominationType": {
                "isMilitary": true
            },
            "number": 2804,
            "organization": "Army",
            "partNumber": "00",
            "receivedDate": "2022-12-07",
            "updateDate": "2022-12-08T05:25:17Z",
            "url": "https://api.congress.gov/v3/nomination/117/2804?format=json"
        },
        {
            "citation": "PN2803",
            "congress": 117,
            "latestAction": {
                "actionDate": "2022-12-07",
                "text": "Received in the Senate and referred to the Committee on Armed Services."
            },
            "nominationType": {
                "isMilitary": true
            },
            "number": 2803,
            "organization": "Army",
            "partNumber": "00",
            "receivedDate": "2022-12-07",
            "updateDate": "2022-12-08T05:25:17Z",
            "url": "https://api.congress.gov/v3/nomination/117/2803?format=json"
        }
    ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| `format` | string (query) - The data format. Value can be xml or json. |
| `offset` | integer (query) - The starting record returned. 0 is the first record. |
| `limit` | integer (query) - The number of records returned. The maximum limit is 250. |
| `fromDateTime` | string (query) - The starting timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |
| `toDateTime` | string (query) - The ending timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |

---

### **GET `/nomination/{congress}`**

**Description**: Returns a list of nominations filtered by the specified congress and sorted by date received from the President.

**Example Request**:

```
https://api.congress.gov/v3/nomination/117?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "nominations": [
        {
            "citation": "PN2804",
            "congress": 117,
            "latestAction": {
                "actionDate": "2022-12-07",
                "text": "Received in the Senate and referred to the Committee on Armed Services."
            },
            "nominationType": {
                "isMilitary": true
            },
            "number": 2804,
            "organization": "Army",
            "partNumber": "00",
            "receivedDate": "2022-12-07",
            "updateDate": "2022-12-08T05:25:17Z",
            "url": "https://api.congress.gov/v3/nomination/117/2804?format=json"
        },
        {
            "citation": "PN2803",
            "congress": 117,
            "latestAction": {
                "actionDate": "2022-12-07",
                "text": "Received in the Senate and referred to the Committee on Armed Services."
            },
            "nominationType": {
                "isMilitary": true
            },
            "number": 2803,
            "organization": "Army",
            "partNumber": "00",
            "receivedDate": "2022-12-07",
            "updateDate": "2022-12-08T05:25:17Z",
            "url": "https://api.congress.gov/v3/nomination/117/2803?format=json"
        }
    ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| `congress` * | integer (path) - The congress number. For example, the value can be 117. |
| `format` | string (query) - The data format. Value can be xml or json. |
| `offset` | integer (query) - The starting record returned. 0 is the first record. |
| `limit` | integer (query) - The number of records returned. The maximum limit is 250. |
| `fromDateTime` | string (query) - The starting timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |
| `toDateTime` | string (query) - The ending timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |

---

### **GET `/nomination/{congress}/{nominationNumber}`**

**Description**: Returns detailed information for a specified nomination.

**Example Request**:

```
https://api.congress.gov/v3/nomination/117/2467?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "nomination": {
        "actions": {
            "count": 1,
            "url": "https://api.congress.gov/v3/nomination/117/2467/actions?format=json"
        },
        "citation": "PN2467",
        "committees": {
            "count": 1,
            "url": "https://api.congress.gov/v3/nomination/117/2467/committees?format=json"
        },
        "congress": 117,
        "isList": true,
        "latestAction": {
            "actionDate": "2022-08-03",
            "text": "Received in the Senate and referred to the Committee on Armed Services."
        },
        "nominees": [
            {
                "introText": "THE FOLLOWING NAMED OFFICERS FOR APPOINTMENT TO THE GRADE INDICATED IN THE UNITED STATES AIR FORCE UNDER TITLE 10, U.S.C., SECTION 624:",
                "nomineeCount": 12,
                "ordinal": 1,
                "organization": "Air Force",
                "positionTitle": "Colonel",
                "url": "https://api.congress.gov/v3/nomination/117/2467/1?format=json"
            }
        ],
        "number": 2467,
        "partNumber": "00",
        "receivedDate": "2022-08-03",
        "updateDate": "2022-08-04T04:25:12Z"
    }
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| `congress` * | integer (path) - The congress number. For example, the value can be 117. |
| `nominationNumber` * | integer (path) - The nomination's assigned number. For example, the value can be 2467. |
| `format` | string (query) - The data format. Value can be xml or json. |

---

### **GET `/nomination/{congress}/{nominationNumber}/{ordinal}`**

**Description**: Returns the list nominees for a position within the nomination.

**Example Request**:

```
https://api.congress.gov/v3/nomination/117/2467/1?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "nominees": [
        {
            "firstName": "JOHN",
            "lastName": "SZCZEPANSKI",
            "middleName": "T.",
            "ordinal": 12
        },
        {
            "firstName": "ERIN",
            "lastName": "REYNOLDS",
            "middleName": "S.",
            "ordinal": 11
        }
    ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| `congress` * | integer (path) - The congress number. For example, the value can be 117. |
| `nominationNumber` * | integer (path) - The nomination's assigned number. For example, the value can be 2467. |
| `ordinal` * | integer (path) - The ordinal number. For example, the value can be 1. |
| `format` | string (query) - The data format. Value can be xml or json. |
| `offset` | integer (query) - The starting record returned. 0 is the first record. |
| `limit` | integer (query) - The number of records returned. The maximum limit is 250. |

---

### **GET `/nomination/{congress}/{nominationNumber}/actions`**

**Description**: Returns the list of actions on a specified nomination.

**Example Request**:

```
https://api.congress.gov/v3/nomination/117/2467/actions?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "actions": [
        {
            "actionCode": "S05120",
            "actionDate": "2022-08-03",
            "committees": [
              {
                "name": "Armed Services Committee",
                "systemCode": "ssas00",
                "url": "https://api.congress.gov/v3/committee/senate/ssas00?format=json"
              }
            ],
            "text": "Received in the Senate and referred to the Committee on Armed Services.",
            "type": "IntroReferral"
        }
    ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| `congress` * | integer (path) - The congress number. For example, the value can be 117. |
| `nominationNumber` * | integer (path) - The nomination's assigned number. For example, the value can be 2467. |
| `format` | string (query) - The data format. Value can be xml or json. |
| `offset` | integer (query) - The starting record returned. 0 is the first record. |
| `limit` | integer (query) - The number of records returned. The maximum limit is 250. |

---

### **GET `/nomination/{congress}/{nominationNumber}/committees`**

**Description**: Returns the list of committees associated with a specified nomination.

**Example Request**:

```
https://api.congress.gov/v3/nomination/117/2467/committees?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "committees": [
        {
            "activities": [
                {
                    "date": "2022-08-03T21:02:58Z",
                    "name": "Referred to"
                }
            ],
            "chamber": "Senate",
            "name": "Armed Services Committee",
            "systemCode": "ssas00",
            "type": "Standing",
            "url": "https://api.congress.gov/v3/committee/senate/ssas00?format=json"
        }
    ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| `congress` * | integer (path) - The congress number. For example, the value can be 117. |
| `nominationNumber` * | integer (path) - The nomination's assigned number. For example, the value can be 2467. |
| `format` | string (query) - The data format. Value can be xml or json. |
| `offset` | integer (query) - The starting record returned. 0 is the first record. |
| `limit` | integer (query) - The number of records returned. The maximum limit is 250. |

---

### **GET `/nomination/{congress}/{nominationNumber}/hearings`**

**Description**: Returns the list of printed hearings associated with a specified nomination.

**Example Request**:

```
https://api.congress.gov/v3/nomination/116/389/hearings?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "hearings": [
        {
          "chamber": "Senate",
          "citation": "S.Hrg.116-38",
          "date": "2019-06-05",
          "jacketNumber": 37106,
          "number": 38
        }
    ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| `congress` * | integer (path) - The congress number. For example, the value can be 116. |
| `nominationNumber` * | integer (path) - The nomination's assigned number. For example, the value can be 389. |
| `format` | string (query) - The data format. Value can be xml or json. |
| `offset` | integer (query) - The starting record returned. 0 is the first record. |
| `limit` | integer (query) - The number of records returned. The maximum limit is 250. |
# **Congress.gov CRS Report API Documentation**

## **Overview**

The Congress.gov CRS Report API provides access to Congressional Research Service (CRS) reports, which are detailed policy and legal analyses prepared for members of Congress.

Base URL: `https://api.congress.gov/v3/crsreport`

All endpoints require an API key provided via `?api_key=[INSERT_KEY]`.

---

## **Endpoints**

### **GET `/crsreport`**

**Description**: Returns Congressional Research Service (CRS) report data from the API.

**Example Request**:

```
https://api.congress.gov/v3/crsreport?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "CRSReports": [
       {
            "contentType": "Reports",
            "id": "R43083",
            "publishDate": "2025-02-05T11:34:25Z",
            "status": "Active",
            "title": "SBA Assistance to Small Business Startups: Client Experiences and Program Impact",
            "updateDate": "2025-02-07T01:36:49Z",
            "url": "http://api.congress.gov/v3/crsreport/R43083",
            "version": 145
        },
        {
            "contentType": "Reports",
            "id": "98-202",
            "publishDate": "2025-02-05T10:41:39Z",
            "status": "Archived",
            "title": "Appropriations for FY1999: Treasury, Postal Service, Executive Office of the President, and General Government",
            "updateDate": "2025-02-05T10:41:39Z",
            "url": "http://api1.test.congress.gov/v3/crsreport/98-202",
            "version": 102
        }
     ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| `format` | string (query) - The data format. Value can be xml or json. |
| `offset` | integer (query) - The starting record returned. 0 is the first record. |
| `limit` | integer (query) - The number of records returned. The maximum limit is 250. |

---

### **GET `/crsreport/{reportNumber}`**

**Description**: Returns detailed information for a specified Congressional Research Service (CRS) report.

**Example Request**:

```
https://api.congress.gov/v3/crsreport/R47175?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "CRSReport": {
            "authors": [
                 {
                     "author": "Megan S. Lynch"
                 }
            ],
            "contentType": "Reports",
            "formats": [
                {
                     "format": "PDF",
                     "url": "https://congress.gov/crs_external_products/R/PDF/R47175/R47175.2.pdf"
                },
                {
                     "format": "HTML",
                     "url": "https://congress.gov/crs_external_products/R/HTML/R47175.html"
                }
            ],
            "id": "R47175",
            "publishDate": "2025-02-05T11:34:31Z",
            "relatedMaterials": [
                {
                              "URL": "https://api.congress.gov/v3/law/93/pub/344",
                              "congress": 93,
                              "number": "93-344",
                              "title": null,
                              "type": "PUB"
                 },
                 {
                              "URL": "https://api.congress.gov/v3/bill/117/HRES/1151",
                              "congress": 117,
                              "number": 1151,
                              "title": "Providing for budget allocations, and for other purposes.",
                              "type": "HRES"
                  },
                  {
                              "URL": "https://api.congress.gov/v3/bill/117/HRES/1151",
                              "congress": 117,
                              "number": 1151,
                              "title": "Providing for budget allocations, and for other purposes.",
                              "type": "HRES"
                  }
             ],
             "status": "Active",
             "summary": "The Congressional Budget Act of 1974 directs Congress to adopt a budget resolution each spring, providing an agreement between the House and Senate on a budget plan for the upcoming fiscal year (and at least four additional years). The annual budget resolution includes certain spending and revenue levels that become enforceable through points of order once both chambers have adopted the resolution.Congress does not always adopt a budget resolution, however, and this may complicate the development and consideration of budgetary legislation. Congress has, therefore, developed an alternative legislative tool, typically referred to as a "deeming resolution" because it is deemed to serve in place of an annual budget resolution for the purposes of establishing enforceable budgetary levels. On June 8, 2022, the House of Representatives adopted H.Res. 1151, a deeming resolution for FY2023. H.Res. 1151 provided a committee spending allocation (302(a) allocation) to the House Appropriations Committee ($1.603 trillion). It also directed the chair of the House Budget Committee to subsequently file a statement in the Congressional Record that includes committee spending allocations for all other committees, as well as aggregate spending and revenue levels. (Those levels were filed on June 21, 2022.) H.Res. 1151 specified that the levels filed in the Congressional Record be consistent with the "most recent baseline of the Congressional Budget Office," meaning that the committee spending allocations (other than for the Appropriations Committee) and the aggregate spending and revenue levels have been set at the levels currently projected under current law. In addition to providing enforceable budgetary levels within the House, H.Res. 1151 grants authority to the chair of the House Budget Committee to "adjust" the budgetary levels provided under the deeming resolution in the future under specified circumstances. In addition, the resolution states that provisions designated as "emergency" shall be effectively exempt from House budgetary rules and specifies that certain accounts may receive advance appropriations for FY2024 and FY2025.",
            "title": "Setting Budgetary Levels: The House's FY2023 Deeming Resolution",
            "topics": [
                {
                    "topic": "Budget &amp; Appropriations Procedure"
                }
            ],
            "updateDate": "2025-02-07T01:36:56Z",
            "url": "congress.gov/crs-report/R47175",
            "version": 102
     }
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| `reportNumber` * | string (path) - The number or ID of the report. For example, R47175. |
| `format` | string (query) - The data format. Value can be xml or json. |

---

## **Congressional MCP Server Implementation**

The Congressional MCP server provides the following resources and tools for accessing CRS Reports:

### **Resources**

- `congress://crs-reports/latest` - Get the most recent CRS reports
- `congress://crs-reports/{report_number}` - Get detailed information for a specific CRS report

### **Tools**

- `search_crs_reports` - Search for CRS reports based on keywords or report number
# **Congress.gov Treaty API Documentation**

## **Overview**

The Congress.gov Treaty API provides access to treaty data, including metadata, actions, committees, and related documents.

Base URL: `https://api.congress.gov/v3/treaty`

All endpoints require an API key provided via `?api_key=[INSERT_KEY]`.

---

## **Endpoints**

### **GET `/treaty`**

**Description**: Returns a list of treaties sorted by date of last update.

**Example Request**:

```
https://api.congress.gov/v3/treaty?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "treaties": [
        {
          "congressReceived": 116,
          "congressConsidered": 116,
          "number": 1,
          "parts": {},
          "suffix": "",
          "topic": "International Law and Organization",
          "transmittedDate": "2022-07-11T00:00:00Z",
          "updateDate": "2022-08-04T02:46:11Z",
          "url": "https://api.congress.gov/v3/treaty/116/1?format=json"
        }
    ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| `format` | string (query) - The data format. Value can be xml or json. |
| `offset` | integer (query) - The starting record returned. 0 is the first record. |
| `limit` | integer (query) - The number of records returned. The maximum limit is 250. |
| `fromDateTime` | string (query) - The starting timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |
| `toDateTime` | string (query) - The ending timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |

---

### **GET `/treaty/{congress}`**

**Description**: Returns a list of treaties for the specified congress, sorted by date of last update.

**Example Request**:

```
https://api.congress.gov/v3/treaty/117?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "treaties": [
        {
          "congressReceived": 116,
          "congressConsidered": 116,
          "number": 1,
          "parts": {},
          "suffix": "",
          "topic": "International Law and Organization",
          "transmittedDate": "2022-07-11T00:00:00Z",
          "updateDate": "2022-08-04T02:46:11Z",
          "url": "https://api.congress.gov/v3/treaty/116/1?format=json"
        }
    ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| `congress` * | integer (path) - The congress number. For example, value can be 117. |
| `format` | string (query) - The data format. Value can be xml or json. |
| `offset` | integer (query) - The starting record returned. 0 is the first record. |
| `limit` | integer (query) - The number of records returned. The maximum limit is 250. |
| `fromDateTime` | string (query) - The starting timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |
| `toDateTime` | string (query) - The ending timestamp to filter by update date. Use format: YYYY-MM-DDT00:00:00Z. |

---

### **GET `/treaty/{congress}/{treatyNumber}`**

**Description**: Returns detailed information for a specified treaty.

**Example Request**:

```
https://api.congress.gov/v3/treaty/117/3?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "request": {
        "congress": "116",
        "contentType": "application/json",
        "format": "json"
    },
    "treaty": {
        "actions": {
            "count": 18,
            "url": "http://api.congress.gov/v3/treaty/116/1/actions?format=json"
        },
        "congressConsidered": 116,
        "congressReceived": 116,
        "countriesParties": [
            {
                "name": "North Macedonia, The Republic of"
            }
        ],
        "inForceDate": null,
        "indexTerms": [
            {
                "name": "116-1"
            },
            {
                "name": "Accession"
            },
            {
                "name": "North Atlantic Treaty of 1949"
            },
            {
                "name": "North Macedonia"
            },
            {
                "name": "North Macedonia, The Republic of"
            },
            {
                "name": "TD116-1"
            },
            {
                "name": "The Republic of North Macedonia"
            },
            {
                "name": "Ex. Rept. 116-5"
            }
        ],
        "number": 1,
        "oldNumber": null,
        "oldNumberDisplayName": null,
        "parts": {},
        "relatedDocs": [
            {
                "citation": "Ex. Rept. 116-5",
                "url": "http://api.congress.gov/v3/committee-report/116/ERPT/5"
            }
        ],
        "resolutionText": "[117] TreatyRes. 6 for TreatyDoc. 117 - 3<p>As approved by the Senate: </p><p><i>Resolved (two-thirds of the Senators present concurring therein),</i></p><p></p><p><b>SECTION 1. SENATE ADVICE AND CONSENT SUBJECT TO DECLARATIONS AND CONDITIONS.</b></p>...",
        "suffix": "",
        "titles": [
            {
                "title": "Protocol to the North Atlantic Treaty of 1949 on the Accession of the Republic of North Macedonia",
                "titleType": "Treaty - Short Title"
            },
            {
                "title": "Protocol to the North Atlantic Treaty of 1949 on the Accession of the Republic of North Macedonia",
                "titleType": "Treaty - Formal Title"
            }
        ],
        "topic": "International Law and Organization",
        "transmittedDate": "2022-07-11T00:00:00Z",
        "updateDate": "2022-08-04T02:46:11Z"
    }
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| `congress` * | integer (path) - The congress number. For example, value can be 117. |
| `treatyNumber` * | integer (path) - The treaty's assigned number. For example, value can be 3. |
| `format` | string (query) - The data format. Value can be xml or json. |

---

### **GET `/treaty/{congress}/{treatyNumber}/{treatySuffix}`**

**Description**: Returns detailed information for a specified partitioned treaty.

**Example Request**:

```
https://api.congress.gov/v3/treaty/114/13/A?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "treaty": {
        "actions": {
            "count": 5,
            "url": "https://api.congress.gov/v3/treaty/114/13/A/actions?format=json"
        },
        "congressConsidered": 115,
        "congressReceived": 114,
        "countriesParties": [
            {
                "name": "Micronesia, Federated States of"
            }
        ],
        "inForceDate": null,
        "indexTerms": [
            {
                "name": "Maritime"
            },
            {
                "name": "Micronesia"
            },
            {
                "name": "Pacific"
            }
        ],
        "number": 13,
        "oldNumber": null,
        "oldNumberDisplayName": null,
        "parts": {
            "count": 2,
            "urls": [
                "https://api.congress.gov/v3/treaty/114/13/B?format=json",
                "https://api.congress.gov/v3/treaty/114/13?format=json"
            ]
        },
        "relatedDocs": [],
        "resolutionText": "[115] TreatyRes. 3 for TreatyDoc. 114 - 13A<p><i>As approved by the Senate: </i></p><p></p><p>Resolved, (two-thirds of the Senators present concurring therein),</p><p><b>SECTION 1. SENATE ADVICE AND CONSENT SUBJECT TO A DECLARATION.</b></p><p>The Senate advises and consents to the ratification of the Treaty between the Government of the United States of America and the Government of the Republic of Kiribati on the Delimitation of Maritime Boundaries, signed at Majuro on September 6, 2013 (the "Treaty") (Treaty Doc 114-13B), subject to the declaration in section 2.</p><p><b>SEC. 2. DECLARATION.</b></p><p>The Senate's advice and consent under section 1 is subject to the following declaration: The Treaty is self-executing.</p><p></p><p></p>",
        "suffix": "A",
        "titles": [
            {
                "title": "Treaty between the Government of the United States of America and the Government of the Federated States of Micronesia on the Delimitation of a Maritime Boundary, signed at Koror on August 1, 2014.",
                "titleType": "Treaty - Formal Title"
            },
            {
                "title": "The Treaty with the Federated States of Micronesia on the Delimitation of a Maritime Boundary",
                "titleType": "Treaty - Short Title"
            }
        ],
        "transmittedDate": "2016-12-09T00:00:00Z",
        "treatyNum": 13,
        "topic": "Maritime Boundaries and Claims",
        "updateDate": "2022-07-12T15:48:45Z"
    }
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| `congress` * | integer (path) - The congress number. For example, the value can be 114. |
| `treatyNumber` * | integer (path) - The treaty's assigned number. For example, the value can be 13. |
| `treatySuffix` * | string (path) - The treaty's partition letter value. For example, the value can be A. |
| `format` | string (query) - The data format. Value can be xml or json. |

---

### **GET `/treaty/{congress}/{treatyNumber}/actions`**

**Description**: Returns the list of actions on a specified treaty.

**Example Request**:

```
https://api.congress.gov/v3/treaty/117/3/actions?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "actions": [
        {
            "actionCode": "S05291",
            "actionDate": "2022-08-03",
            "committee": null,
            "text": "Resolution of advice and consent to ratification agreed to as amended in Senate by Yea-Nay Vote. 95 - 1. Record Vote Number: 282.",
            "type": "Floor"
        },
        {
            "actionCode": "S05311",
            "actionDate": "2022-08-03",
            "committee": null,
            "text": "Treaty moved through its parliamentary stages up to and including presentation of the resolution of advice and consent to ratification.",
            "type": "Floor"
        }
    ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| `congress` * | integer (path) - The congress number. For example, the value can be 117. |
| `treatyNumber` * | integer (path) - The treaty's assigned number. For example, the value can be 3. |
| `format` | string (query) - The data format. Value can be xml or json. |
| `offset` | integer (query) - The starting record returned. 0 is the first record. |
| `limit` | integer (query) - The number of records returned. The maximum limit is 250. |

---

### **GET `/treaty/{congress}/{treatyNumber}/{treatySuffix}/actions`**

**Description**: Returns the list of actions on a specified partitioned treaty.

**Example Request**:

```
https://api.congress.gov/v3/treaty/114/13/A/actions?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "actions": [
        {
            "actionCode": "S05291",
            "actionDate": "2018-07-26",
            "committee": null,
            "text": "Resolution of advice and consent to ratification agreed to in Senate by Division Vote.",
            "type": "Floor"
        },
        {
            "actionCode": "S05311",
            "actionDate": "2018-07-26",
            "committee": null,
            "text": "Treaty moved through its parliamentary stages up to and including presentation of the resolution of advice and consent to ratification.",
            "type": "Floor"
        }
    ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| `congress` * | integer (path) - The congress number. For example, the value can be 114. |
| `treatyNumber` * | integer (path) - The treaty's assigned number. For example, the value can be 13. |
| `treatySuffix` * | string (path) - The treaty's partition letter value. For example, the value can be A. |
| `format` | string (query) - The data format. Value can be xml or json. |
| `offset` | integer (query) - The starting record returned. 0 is the first record. |
| `limit` | integer (query) - The number of records returned. The maximum limit is 250. |

---

### **GET `/treaty/{congress}/{treatyNumber}/committees`**

**Description**: Returns the list of committees associated with a specified treaty.

**Example Request**:

```
https://api.congress.gov/v3/treaty/116/3/committees?api_key=[INSERT_KEY]
```

**Example Response**:

```json
{
    "treatyCommittees": [
        {
            "activities": [
                {
                    "date": "2020-06-18T20:19:22Z",
                    "name": "Referred to"
                }
            ],
            "chamber": "Senate",
            "name": "Foreign Relations Committee",
            "subcommittees": [],
            "systemCode": "ssfr00",
            "type": "Standing",
            "url": "https://api.congress.gov/v3/committee/senate/ssfr00?format=json"
        }
    ]
}
```

**Parameters**:

| Name | Description |
|------|-------------|
| `congress` * | integer (path) - The congress number. For example, the value can be 116. |
| `treatyNumber` * | integer (path) - The treaty's assigned number. For example, the value can be 3. |
| `format` | string (query) - The data format. Value can be xml or json. |
| `offset` | integer (query) - The starting record returned. 0 is the first record. |
| `limit` | integer (query) - The number of records returned. The maximum limit is 250. |

---

## **Congressional MCP Server Implementation**

The Congressional MCP server will provide the following resources and tools for accessing Treaty data:

### **Resources**

- `congress://treaties/latest` - Get the most recent treaties
- `congress://treaties/{congress}` - Get treaties from a specific Congress
- `congress://treaties/{congress}/{treaty_number}` - Get details for a specific treaty
- `congress://treaties/{congress}/{treaty_number}/{treaty_suffix}` - Get details for a specific partitioned treaty

### **Tools**

- `search_treaties` - Search for treaties based on various criteria
- `get_treaty_actions` - Get actions for a specific treaty
- `get_treaty_committees` - Get committees for a specific treaty
