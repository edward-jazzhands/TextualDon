Here's a list of some basic cool things you can do with Beautifulsoup commands and parser:   
### soup.title   
- Finds the first paragraph tag
### soup.title.name
### soup.title.string
### soup.title.parent.name
### soup.p 
- Finds first paragraph tag
### for p in soup.find_all('p')
- Finds all paragraph tags
### p.decompose()
- Removes the paragraph tag and its contents
### p.get_text()
- Gets the text of the paragraph tag
### p.get_text(strip=True)
- Gets the text of the paragraph tag without whitespace