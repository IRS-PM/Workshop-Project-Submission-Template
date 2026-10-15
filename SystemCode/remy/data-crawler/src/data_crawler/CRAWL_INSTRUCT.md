**Fetch all products**
- All products are located in <div> class with data-impressiontype="PRODUCT_IMPRESSION"
- The price can be extracted from the child <span> class ends with "iNLBGt" (for example: "sc-ab6170a9-1 iNLBGt")
- Product name can be extracted from the child <span> class ends with "gpnjpI" (for example "sc-ab6170a9-1 gpnjpI")
- Selling quantity (like 90g) (if have) can be extracted from the child <span> class ends with "iIDbJm" (for example "sc-e94e62e6-1 iIDbJm") - Also Halal note can be extracted from this (It would be divided into 2 spans with one being data-testid="dietary-attributes-separator" and then text is Halal)

**Where to crawl**
https://www.fairprice.com.sg/category/fruits-vegetables
https://www.fairprice.com.sg/category/meat-seafood
https://www.fairprice.com.sg/category/dairy-chilled-eggs
https://www.fairprice.com.sg/category/rice-noodles-cooking-ingredients
https://www.fairprice.com.sg/category/frozen

**For crawling unmatched (using search-crawl)**
- Click to each item's corresponding page
- Find <a> with class ends with "cuemoG" (for example "sc-1b42ef49-1 cuemoG"). You got the href="/category/<corresponding category that you will extract here>"