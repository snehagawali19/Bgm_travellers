# **Cursor Prompt: Build a Basic IntrCity-Inspired Bus Booking UI**

Act as a senior UI/UX designer and frontend developer.

I want to redesign my existing travel agency website to have a clean, modern intercity bus booking interface inspired by IntrCity SmartBus. For now, focus ONLY on the homepage and basic booking interface. I will add advanced functionality later.

## **1\. First inspect the existing project**

* Inspect the current repository and identify the framework, components, styling system, and existing routes.  
* Reuse the existing stack and preserve working functionality.  
* Do not unnecessarily recreate the project or replace the entire codebase.  
* Tell me which files you intend to modify, then implement the UI.

## **2\. Homepage design**

Create a polished, minimalist, responsive homepage with:

### **Header**

* Travel agency logo placeholder on the left.  
* Navigation: Home, My Bookings, Contact Us.  
* Login button or simple account placeholder.  
* Clean white background with subtle borders.

### **Hero section**

* Large headline: "Your Journey, Made Comfortable."  
* Supporting text: "Book your next bus journey with ease."  
* Use a tasteful intercity bus photograph as a background or side image.  
* Maintain a clean, modern layout with generous whitespace.

### **Bus search card**

Create a prominent booking card containing:

* From: Belgaum (Belagavi).  
* To: Bengaluru.  
* A swap button between the locations.  
* Travel date picker.  
* Search Buses button.

For now, show only Belgaum and Bengaluru as the available cities. Keep the components reusable so I can add Mumbai or other cities later.

The form should have basic client-side validation and a working swap button. The search button can navigate to a simple placeholder results page or display a clear message if the backend is not yet implemented.

### **Additional homepage sections**

* Why Travel With Us: Comfortable Travel, Easy Booking, Reliable Service.  
* Our Route: Belgaum ↔ Bengaluru.  
* A simple travel information section.  
* Frequently Asked Questions.  
* Footer with contact placeholders, navigation links, and policy links.

## **3\. Visual style**

Use a professional Indian travel-startup aesthetic:

* White or warm off-white background.  
* Deep navy text.  
* One restrained accent color, such as teal or orange.  
* Modern typography.  
* Rounded booking cards.  
* Subtle shadows and borders.  
* Clear spacing and visual hierarchy.  
* Responsive layouts for desktop, tablet, and mobile.  
* Accessible color contrast and visible keyboard focus states.

Do not overdesign the page. Keep it minimal and easy for me to customize later.

Use original branding and assets. Treat IntrCity only as a general visual reference; do not copy its logo, proprietary assets, or exact page design.

## **4\. Basic interface behavior**

Implement:

* Working From/To swap button.  
* Date selection.  
* Prevent selecting a past travel date.  
* Basic validation before searching.  
* Responsive navigation.  
* Reusable components for the search card, header, footer, and route section.  
* A basic search-results placeholder that displays the selected route and date.

Do not pretend that real bus availability or live fares exist until an API is connected.

## **5\. Keep the project easy to extend**

* Use the project's existing frontend framework.  
* Use reusable components and clean file organization.  
* Keep the list of supported cities in one configurable location.  
* Avoid hardcoding route options across multiple components.  
* Keep business logic separate from visual components.  
* Do not implement a complex backend, payment gateway, seat-locking system, admin dashboard, or refund engine in this task.  
* Do not remove existing backend code or integrations.

## **6\. Completion requirements**

* Implement the changes directly in the existing project.  
* Run the available build or lint commands.  
* Fix any errors introduced by the changes.  
* Verify the homepage on desktop and mobile layouts.  
* Summarize which files were modified and how to run the project.  
* Clearly identify any placeholder features.

Focus on delivering a beautiful, functional homepage and basic booking interface that I can customize later.

Before coding, study the public IntrCity SmartBus website and its booking journey as a visual and functional reference. Recreate the same general quality of user experience and familiar intercity booking flow using original code, branding, components, and assets.

Prioritize the home page, route/date search, trip results, seat-selection interface, passenger details, checkout, booking confirmation, and customer support.

Customize the website for our operator:

* Initial routes: Belgaum ↔ Bengaluru only.  
* Initial fleet: one bus.  
* Future expansion: multiple buses, cities, routes, and scheduled trips.  
* Payment gateway: Razorpay.  
* Admin dashboard: manage buses, trips, fares, seat inventory, bookings, payments, and refunds.

Do not merely create a landing-page mockup. Build the functional frontend, backend, database, booking workflow, and payment integration. Where production credentials or actual bus information are missing, use clearly labeled test data and safe placeholders.

Start by presenting a concise design breakdown and implementation plan, then build the application incrementally and test each stage.

**CURSOR MASTER PROMPT — Scalable Bus Booking MVP**

Act as a senior full-stack engineer and software architect. Build a complete, responsive bus-ticket booking website for a small Indian travel operator.

The business currently operates ONE bus on ONE route: Belgaum (Belagavi) ↔ Bengaluru. A second bus may be added within two months. Future routes may include Bengaluru ↔ Mumbai and Belgaum ↔ Mumbai.Build only the features needed for the initial launch, but design the backend and database so that adding buses, routes, cities, and trips later does not require rewriting the application.The result must be a working full-stack application, not just a UI prototype.

## **1\. Core business scope**

### **Launch requirements**

* One physical bus.  
* One route connecting Belgaum and Bengaluru, with trips in either direction.  
* Admin-configurable departure times, travel dates, fares, boarding points, dropping points, and seat layouts.  
* Customer trip search.  
* Seat selection and temporary seat reservation.  
* Passenger details and checkout.  
* Razorpay payment integration.  
* Booking confirmation, PNR, and e-ticket.  
* Customer booking lookup and cancellation requests.  
* Admin dashboard for trips, seats, bookings, payments, and refunds.

Do not assume that the bus operates every day. The admin must explicitly publish the dates and departures on which tickets can be sold.

### **Future expansion requirements**

The architecture must support:

* Multiple physical buses.  
* Multiple routes and cities.  
* Multiple scheduled trips on the same route.  
* Different buses assigned to different trips.  
* Different seat layouts and capacities for different buses.  
* Different fares and cancellation policies where configured.  
* Adding Bengaluru–Mumbai or Belgaum–Mumbai without hardcoding the cities into business logic.

Do not build an airline-style network management system or a complex aggregator. Implement the minimum flexible model required for this small operator.

## **2\. Technology stack**

Use:

Frontend:

* Next.js App Router.  
* TypeScript.  
* Tailwind CSS.  
* Responsive, accessible components.

Backend:

* Python FastAPI.  
* Pydantic.  
* SQLAlchemy 2.x.  
* Alembic migrations.

Database:

* PostgreSQL.

Payments:

* Razorpay hosted checkout.  
* Server-side payment verification.  
* Signed webhook handling.  
* Refund API integration.

Deployment:

* Vercel for the frontend.  
* Render or a comparable managed platform for FastAPI.  
* Managed PostgreSQL.

Use stable, compatible dependencies and document their versions.

## **3\. Scalable data model**

Do not hardcode one bus or one route in application logic.

Create these entities with appropriate relationships, constraints, and indexes:

### **City**

Fields:

* id  
* name  
* slug  
* state  
* country  
* active

Seed:

* Belgaum/Belagavi  
* Bengaluru

Use one canonical city record for each city. Support alternate display names or search aliases where needed, rather than creating duplicate cities for spelling variants.

### **Bus**

Fields:

* id  
* registration\_number  
* display\_name  
* bus\_type  
* seat\_capacity  
* status  
* amenities  
* created\_at  
* updated\_at

The database must support additional buses without schema changes.

### **BusSeat**

Fields:

* id  
* bus\_id  
* seat\_number  
* seat\_type  
* deck or position metadata where applicable  
* active

Create a configurable seat layout based on the actual bus. Never assume every bus has the same capacity or layout.

### **Route**

Fields:

* id  
* origin\_city\_id  
* destination\_city\_id  
* route\_name  
* estimated\_duration\_minutes  
* active

Represent each travel direction as a distinct directed route. For launch, create Belgaum → Bengaluru and Bengaluru → Belgaum.

Add a database uniqueness rule to prevent duplicate active route definitions for the same origin and destination.

### **RouteStop**

Fields:

* id  
* route\_id  
* city\_id where applicable  
* stop\_name  
* address  
* pickup\_allowed  
* dropoff\_allowed  
* display\_order  
* active

Support multiple boarding and dropping points per route.

### **Trip**

Fields:

* id  
* route\_id  
* bus\_id  
* departure\_datetime  
* estimated\_arrival\_datetime  
* base\_fare\_paise  
* status  
* published\_at  
* created\_at

A trip represents ONE scheduled departure, not a permanent route.

The same bus may have multiple trips on different dates. Future trips may be assigned to another bus.

Validate that the bus is available for the trip and is not already assigned to a conflicting trip. Prevent overlapping assignments and enforce operational turnaround time through backend validation.

### **Seat inventory and holds**

Implement trip-specific seat inventory using the assigned bus's seats.

Use a reliable transactional model for:

* Available seats.  
* Temporarily held seats.  
* Confirmed bookings.  
* Administratively blocked seats.

Seat availability must be derived from database state. Do not store a single global seat status on BusSeat and reuse it for every trip.

### **Booking**

Fields:

* id  
* public\_reference  
* pnr  
* trip\_id  
* customer contact details  
* total\_amount\_paise  
* booking\_status  
* created\_at  
* updated\_at

### **BookingSeat**

Fields:

* id  
* booking\_id  
* trip\_id  
* bus\_seat\_id  
* passenger details or a relationship to a passenger record  
* fare\_snapshot\_paise

Use transactional locking and database constraints so two active bookings cannot claim the same seat for the same trip.

### **Payments, webhooks, cancellations, refunds and audit logs**

Create separate records for payment orders, individual payment transactions, webhook event IDs, cancellation requests, refunds, and administrator actions.

Use integer paise for all INR monetary amounts. Never use floating-point values for money.

Use UTC timestamps internally and display local travel times in Asia/Kolkata.

## **4\. Customer website**

Create the following pages.

### **Home**

* Original brand identity.  
* From and To selectors populated from active cities and routes.  
* Initially show Belgaum and Bengaluru only.  
* Swap-origin-and-destination button.  
* Travel date selector.  
* Passenger count.  
* Search button.  
* Trip information, support, FAQs and footer.

The interface must not show Mumbai or any future city as bookable until the relevant route and trips have been configured and published by the admin.

### **Search results**

* Display published trips matching the selected route and date.  
* Show departure, estimated arrival, duration, fare, bus type, and available seats.  
* Display pickup and drop-off options.  
* Show a clear empty state if no trip exists.  
* Never invent availability or fares.

### **Seat selection**

* Display the actual assigned bus's seat layout.  
* Show available, selected, held, booked and blocked states.  
* Use server-controlled seat holds with expiry.  
* Refresh or revalidate availability before creating a booking.  
* Calculate fares on the backend.

### **Passenger details and checkout**

* Collect required passenger information.  
* Validate email and mobile number.  
* Show fare breakdown and cancellation terms.  
* Create a pending booking and payment order on the backend.  
* Integrate Razorpay hosted checkout.  
* Never trust client-supplied prices.

### **Booking confirmation**

* Confirm only after verified payment and successful seat allocation.  
* Generate a unique PNR.  
* Provide a printable/downloadable ticket and QR verification reference.  
* Display passenger, seat, route, departure and pickup details.

### **My bookings**

* Allow secure retrieval of a customer's booking.  
* Provide ticket access and cancellation requests.  
* Protect customer records from unauthorized access.

## **5\. Admin dashboard**

Implement secure server-side authorization for all admin endpoints.

The dashboard must allow the operator to:

* Create and edit cities.  
* Create routes between existing cities.  
* Activate or deactivate routes.  
* Register additional buses.  
* Configure the actual seat layout for each bus.  
* Create and publish scheduled trips.  
* Assign a bus to a trip.  
* Configure departure and arrival times.  
* Set fares and boarding/drop-off stops.  
* View bookings and passenger manifests.  
* Block seats for specific trips.  
* Cancel a trip.  
* Review payment transactions and exceptions.  
* Request and track refunds.  
* Export a trip's passenger list as CSV.

For the first release, the admin may manually create and publish trips. Automated recurring schedule generation is not required.

Protect against deactivating a route or bus in a way that silently invalidates already-confirmed trips. Require an explicit resolution for affected bookings.

## **6\. Payment and booking correctness**

Implement the following workflow:

1. Customer selects a published trip.  
2. Backend checks current seat availability.  
3. Backend creates an expiring seat hold and pending booking transactionally.  
4. Backend calculates the amount and creates a Razorpay order.  
5. Customer completes hosted checkout.  
6. Backend verifies the payment signature and actual gateway payment status.  
7. Signed webhooks update payment records idempotently.  
8. Booking and seat confirmation occur transactionally.  
9. PNR and ticket become available only after confirmation.

Handle:

* Payment failures.  
* Delayed confirmation.  
* Duplicate checkout submissions.  
* Duplicate webhook events.  
* Two customers selecting the same seat.  
* A payment succeeding after the seat hold expires.  
* Two distinct captured payments for one booking.  
* Failed, pending and successful refunds.

Do not treat a repeated webhook as proof of a repeated payment. Use gateway payment IDs to identify distinct transactions.

Do not automatically charge again when a payment result is uncertain. Reconcile with the gateway first.

If a payment succeeds but the seat cannot be secured, place the booking into a review/exception state and follow the configured refund process. Never issue a conflicting ticket.

Use Razorpay Test Mode for development. Keep live payment processing disabled until merchant approval, production credentials, webhooks, and acceptance tests are complete.

## **7\. Cancellation and refund management**

Build a configurable cancellation policy, but do not invent the operator's final commercial terms.

Support full-booking cancellation for the MVP.

* Calculate eligibility on the backend.  
* Show the estimated refund before confirmation.  
* Save the policy version and refund calculation.  
* Prevent duplicate cancellation processing.  
* Track refund status separately from booking status.  
* Store gateway refund references.  
* Never mark a refund complete before confirmation from the gateway.  
* Provide admin reconciliation for failed or delayed refunds.  
* For operator-cancelled trips, identify affected bookings and apply the approved policy.  
* Notify customers only through configured notification services.

Partial cancellations, rescheduling and promotional offers are future enhancements unless time permits reliable implementation.

## **8\. Security and reliability**

Implement:

* Secure administrator authentication.  
* Password hashing.  
* Server-side authorization.  
* Rate limiting.  
* Input validation.  
* CSRF protection where cookie-based authentication is used.  
* Secure cookies and HTTPS in production.  
* CORS restricted to known origins.  
* Environment-variable-based secrets.  
* Signed webhook verification using the exact raw request body.  
* Database transactions and uniqueness constraints.  
* Idempotent payment, booking and refund operations.  
* Structured logs with sensitive information redacted.  
* Database migrations and backups.  
* Health checks and documented recovery procedures.

Never store card numbers or CVVs. Never expose Razorpay secrets in frontend code. Never trust frontend-only role checks.

## **9\. Future expansion acceptance criteria**

The project is considered expansion-ready only if all of the following work without code changes to the core booking flow:

1. Admin can add Bus 2 and configure its independent seat layout.  
2. Admin can assign Bus 2 to a new trip.  
3. Customers can book seats on Bus 1 and Bus 2 independently.  
4. Booking a seat on one trip does not block the same physical seat on another non-conflicting trip.  
5. Admin can create Mumbai as a city.  
6. Admin can create Bengaluru → Mumbai and Belgaum → Mumbai routes using existing city records.  
7. Newly published trips appear automatically in search results.  
8. Existing routes, PNRs, payments and bookings continue working after new routes are added.  
9. City names and route options are populated from the database rather than hardcoded frontend arrays.  
10. The application prevents assignment of one bus to overlapping trips.

## **10\. Testing and deployment**

Write automated tests for:

* Both initial route directions.  
* No scheduled trip.  
* Seat holds and expiration.  
* Concurrent seat reservations.  
* Payment success, failure and delayed confirmation.  
* Duplicate webhook processing.  
* Duplicate captured payments.  
* Refund status transitions.  
* Unauthorized access to admin functions.  
* Access to another customer's booking.  
* Bus conflicts and overlapping trip assignments.  
* Adding a second bus.  
* Adding a new city and route.  
* Existing bookings remaining valid after expansion.

Use a separate test database and a simulated payment provider for automated tests.

Provide:

* Complete source code.  
* Database migrations and seed scripts.  
* `.env.example` containing placeholders only.  
* README with exact setup and deployment commands.  
* API documentation.  
* Automated tests.  
* Razorpay Test Mode instructions.  
* Admin setup guide.  
* Production deployment checklist.  
* Known limitations and handover documentation.

## **11\. Two-week delivery priorities**

Days 1–2: Architecture, schema, migrations, branding and initial city/route setup.

Days 3–5: Trip search, seat inventory, transactional holds, passenger details and booking creation.

Days 6–8: Razorpay Test Mode, verification, webhooks, PNR and ticket generation.

Days 9–10: Admin dashboard, cancellation and refund tracking.

Days 11–12: Security, payment edge cases and automated tests.

Days 13–14: Staging deployment, mobile testing, second-bus simulation, new-city simulation and handover.

Implement the core workflow in small stages. Run tests and builds regularly. Do not claim a feature is complete if it is only mocked.

Start by inspecting the existing repository, documenting the architecture and implementation checklist, then build the working MVP. Prioritize booking correctness, payment integrity, security and future extensibility over unnecessary features.

