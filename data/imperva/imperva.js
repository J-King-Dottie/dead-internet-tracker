window.__IMPERVA_SNAPSHOT__ = {
  "chartKey": "imperva-traffic",
  "title": "Imperva traffic profile",
  "description": "This tracks Imperva's published traffic split over time. For this chart, automated traffic means good bot plus bad bot. It matters because it shows automation overtaking humans in a large observed slice of the web.",
  "source": "Imperva Bad Bot Report 2024 and 2025",
  "lastRefreshed": "2026-04-22",
  "method": "We compile the annual traffic profile Imperva publishes in its Bad Bot Report, then combine good bot and bad bot into one automated line. The 2024 point comes from the 2025 report update.",
  "caveats": "This is broader than the Cloudflare chart. Cloudflare above tracks AI bot traffic only; this chart tracks all automation. The levels differ because the metric is broader and the two companies see different slices of the web.",
  "xValues": [
    "2013",
    "2014",
    "2015",
    "2016",
    "2017",
    "2018",
    "2019",
    "2020",
    "2021",
    "2022",
    "2023",
    "2024"
  ],
  "axisValueFormat": "percent1",
  "tooltipValueFormat": "percent1",
  "series": [
    {
      "name": "Bad bot",
      "color": "#ff6f7c",
      "values": [
        23.6,
        22.8,
        18.6,
        19.9,
        21.8,
        20.4,
        24.1,
        25.6,
        27.7,
        30.2,
        32.0,
        37.0
      ]
    },
    {
      "name": "Good bot",
      "color": "#ffd36a",
      "values": [
        19.4,
        36.3,
        27.0,
        18.8,
        20.4,
        17.5,
        13.1,
        15.2,
        14.6,
        17.3,
        17.6,
        14.0
      ]
    },
    {
      "name": "Human",
      "color": "#58e6ff",
      "values": [
        57.0,
        40.9,
        54.4,
        61.3,
        57.8,
        62.1,
        62.8,
        59.2,
        57.7,
        52.6,
        50.4,
        49.0
      ]
    }
  ]
};
