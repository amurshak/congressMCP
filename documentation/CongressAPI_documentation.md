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

## **Response Codes**

* `200` – Successful operation  
* `400` – Invalid status value

---

**Note**: All responses support `application/xml` and `application/json` content types depending on the `format` parameter.

For full integration, ensure proper authentication using your API key in each request.