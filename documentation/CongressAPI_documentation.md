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

## **Response Codes**

* `200` – Successful operation  
* `400` – Invalid status value

---

**Note**: All responses support `application/xml` and `application/json` content types depending on the `format` parameter.

For full integration, ensure proper authentication using your API key in each request.