# Outside Connections and Follett Destiny

**URL:** https://www.thelibrarianedge.com/libedge/2013/11/outside-connections-and-follett-destiny.html  
**Published:** 2013-11-01  
**Author:** Katie Day  
**Word Count:** 1285

---

If I could wave a magic wand and improve Follett Destiny as a school library catalog, it would be to improve ways of linking and looking into it.

Here are a few ways to ameliorate the situation.

1)  Share a Destiny link -- the need to add the all-important 'site' information

Have you ever wanted to send a Destiny link to a title, resource list, or copy category to someone?  If so, you know you HAVE TO add:

&site=NUMBER

to the end of the link, where NUMBER is usually 100, 101, 102, 103, etc.

We host our own catalog, so that's all we have to do.  I just learned that if Follett hosts your catalog, you also have to add:

&context=BLAH

For example:  &context=saas18_8553630&site=100

You can see your particular site information by hovering over the link that gets you into your particular catalog.  For example, our Dover Secondary library is site 100, our Dover Primary library is site 101, our East Primary library is 102, and our East Secondary library is 103.  So that information is added to any link we send to anyone.

Update 12Apr14:

If Follett hosts your catalog and you need to find your CONTEXT number, look at the URL when you see all your catalogs displayed -- and it will be at the end of the URL:

2)  Get a Destiny link -- to a set of search results

If you want to send someone a "canned" ("tinned"?) search -- such that they can dynamically search the catalog by clicking on a link, you need to edit the URL.

For example, suppose I want to send someone a link that will do a keyword search on "economics".  I put "economics" in the Basic Search box and press Enter.  The URL that results is not reproducible -- you can't send it to someone and get the same results.  Instead you need to choose "Refine your search" and work with that URL.

When you get that URL, you need to change the word "present" to "handle":

Lastly, I have to add the site/context info, e.g., here is the final URL.

http://catalog.uwcsea.edu.sg

/cataloging/servlet/

handle

basicsearchform.do?keywordText=

economics

&siteTypeID=-2&searchType=keyword&siteID=&includeLibrary=true&includeMedia=false&mediaSiteID=&doNotSaveSearchHistory=false&awardGroupID=-1

&site=103

The URL above

will do a keyword search on "economics" for the East Second Library of UWCSEA and present the results.

Note:  You can also use DQL (Destiny Query Language) to do a more complicated search out of the Basic search box (because you can't access meaningful URLs based on an Advanced Search).

See the Destiny Help system for more information, e.g.,

3)  Goodreads -- how to click to check if you already have a Goodreads book in your Destiny catalog

First, find a book in Goodreads.  On the Title information page, look for "online stores" and "book links" at the bottom.  It's the "Book Links" bit that you (and your patrons) can customize to go to your school's Destiny catalog to check availability.

Angie Erickson and I presented a workshop on

"Geeking out with Goodreads"

in September at the Google Apps Summit here in Singapore -- and put "how to" information about integration with Follett Destiny up on a Google Site page here:

https://sites.google.com/site/geekingoutwithgoodreads/library-catalog-interfaces

4)  Book Cover Displays -- mirroring bits of your collection via Goodreads or LibraryThing or showing "Latest Arrivals" via Pinterest

Many people use Goodreads or LibraryThing to generate book display widgets for parts of their catalog.

Basically, you reproduce a Resource List or Copy Category (i.e., a list of books) in your catalog into Goodreads or LibraryThing or Pinterest -- and then put them on a shelf or board or tag them.

E.g., here is the 2013-2014 Red Dot books for Older Readers -- display out of Goodreads:

ISLN\ \(Int'l\ School\ Library\ Network\)'s bookshelf: 2013-2014-short-list-older

ISLN (Int'l School Library Network) Singapore's favorite books »

Share

book reviews

and ratings with ISLN (Int'l School Library Network), and even join a

book club

on Goodreads.

Update 12Apr14:

If you "pin" books from within your Destiny catalog (adding the &site=xxx as per above), then when users click through on the board, they will be taken to the title in your catalog.

Pinterest, unlike Goodreads and LibraryThing, is a time-sensitive -- last in, first out -- list.  So it's perfect for showing things like "Latest Arrivals". (In Destiny Quest, users can see latest arrivals, but only 10 or so and you can't control what is on that list.   Via Pinterest, you can choose the books to advertise.

And here are some links to Pinterest boards that show our latest arrivals:

New -- History books -- East

New -- Science books -- East

New -- Economic books -- East

5)  LibraryThing for Libraries -- Book Display Widgets -- linking back to Destiny

LibraryThing for Libraries

has a javascript

Book Widget generator available via Bowker

for about US$ 400 -- which allows you to create any number of book display widgets in four different styles that will let people click on a book cover and go directly to that item in your school catalog.

We're now using it to get beautiful displays of booklists on our Libguide pages, e.g., see our

Economics: Introduction: Books & Physical Resources

and our

Mathematics: Introduction: Books & Physical Resources

guides.

The widget can take a variety of inputs -- as the screenshot to the right shows.

If you want to have the book covers displayed link back to your own catalog -- you need to use the "LibraryThing.com User".  When you buy the widget generator, you automatically get a LibraryThing account to put books into.  The widget works off LibraryThing "Collections" -- so when you enter or import titles, put them in a Collection.

If you have a Destiny Resource List and want those titles imported into LibraryThing, you can run a "Title/Copy List" report out of Destiny -- which includes the ISBN of copies. When the report is displayed, select all and copy the whole text output.  Then in LibraryThing go to "Add Books" then "Import Books" -- and paste that text into the "Grab ISBN" box.  Identify what collection you want them imported into -- then import.

You can then create a widget based on that collection.

You can also dump your whole school catalog as MARC records out of Destiny - and LibraryThing will upload them in batch mode -- though you can't identify tags or collections upon import.

In order to have the widget link back to your catalog, you have to tell LibraryThing how to search your catalog using a URL, e.g.,

ISBN search:

http://catalog.uwcsea.edu.sg

/cataloging/servlet/handlenumbersearchform.do?

searchOption=3

&searchText=

MAGICNUMBER

&includeLibrary=true&includeMedia=false&siteTypeID=-2&siteID=&mediaSiteID=&doNotSaveSearchHistory=false&awardGroupID=-1

&site=103

Title search:

http://catalog.uwcsea.edu.sg

/cataloging/servlet/handlebasicsearchform.do?keywordText=

KEYWORDS

&siteTypeID=101&searchType=title&siteID=&includeLibrary=true&includeMedia=false&mediaSiteID=&doNotSaveSearchHistory=false&awardGroupID=-1

&site=103

Access-based URL:

http://catalog.uwcsea.edu.sg

/cataloging/servlet/presenttitledetailform.do?siteTypeID=101&siteID=&includeLibrary=true&includeMedia=false&mediaSiteID=&bibID=

ACCESSION

&awardGroupID=-1

&site=103

After you get these Global Configurations set up, creating the widget is straight-forward.

Here are the four styles available:

3D Carousel example:

Dynamic Grid example:

Carousel example:

Scrolling example:

NB:  As it's javascript, it's not possible to embed these widgets into Google Sites nor in the Destiny HTML homepage.

6)  Destiny Homepage -- call numbers and collections....

Last but not least, I think we all should be providing better clues about the structure of our catalogs on our Destiny homepages.

When I get to somebody's catalog start page, I have no way of knowing how many books they have or how they've organized their collections.  So I'll look at Resource Lists and Visual Search lists, but if people haven't create any -- then it's a blind search box and I have to guess.

Ideally I'd like to create a map showing my library's layout and physical collections as well as digital resources -- and have that on my homepage.

Until I get around to to doing that, I list all the major call number prefixes on

our Destiny Home Page

.
