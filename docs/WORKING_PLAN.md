# Hallway working plan

Updated November 9, 2026 from Matt's product decisions. This is the current source
of truth for product scope and build order. It supersedes conflicting product
choices in the older pre-conference, design, and implementation plans.
[API.md](API.md) remains the contract for implemented endpoints. Planned features
below are not claims of completed functionality.

## Product promise

**RSVP on Luma. Find your people on Hallway. Have a plan to walk in together.**

Help people find an initial group before a conference, arrive with familiar
people, expand those relationships during the event, and continue afterward.
Community organizers help their members participate. The graph helps create
and maintain useful introductions and arrival plans.

The attendance hypothesis is that an accepted arrival plan and a welcoming
connection can help more registrants attend. This needs testing. Do not assume
every absence is caused by social discomfort or claim reduced no-shows without
evidence. People must be able to cancel without punishment.

## Before, during, and after

| Stage | Attendee experience | Organizer experience |
| --- | --- | --- |
| Before | Join chosen communities, share asks and offers, accept a group, start an icebreaker, and agree on an arrival plan. | Invite communities, share the event, and see aggregate progress toward accepted plans. |
| During | Arrive with the group, use introductions to meet new people, join conversations, and track personal goals. | Help willing attendees who request an introduction and see aggregate check-ins and room activity. |
| After | Review people met and goals pursued, keep chosen conversations open, and plan another meetup or event. | Understand participation and voluntary feedback without exposing private social preferences. |

## Community signup and event sharing

1. A community representative creates a profile with its name, description, and
   private organizer contact, then associates it with a Luma event URL.
2. Hallway provides a shareable community invitation page for that event.
3. A member follows the link, RSVPs through Luma, and separately chooses to join
   the community's Hallway group. A Hallway membership does not grant a Luma ticket.
4. Members can invite existing friends and find relevant people through asks,
   offers, interests, and communities they choose.
5. The representative can maintain invitation and meeting information. Access to
   member information follows member consent; private asks, contact details,
   preferences, and affiliations are not automatically exposed to representatives.

Examples of communities include Girls Who Code, Latinos Who Code, universities,
local meetups, and professional associations. Membership is self-selected, never
inferred from a person's name, appearance, or background. Allow multiple
memberships and an equally useful route for attendees without a community.
Verify control of organizer editing links or accounts before allowing edits.

## Communities, arrival groups, and connections

- A **community** is an affiliation that may span events and include many people.
- An **arrival group**, also called a crew, is a small set of people who choose to
  arrive or participate together for a particular event.
- A **suggested introduction** is a recommendation, not an accepted relationship.
- An **accepted plan** records people agreeing to a meeting time and place.
- A **confirmed meeting** records an interaction, distinct from event attendance.

Match asks against offers in both directions, with interests and chosen
communities as additional signals. Recommend five people before arrival, then
up to three useful new people, groups, or conversations as the event progresses.
Explain recommendations using actual matching evidence. An LLM can suggest an
icebreaker but must not invent the reason for a match.

Suggest arrival groups; let people accept, decline, invite a friend, switch, or
leave. Respect participants' chosen group limits even under concurrent joins.
Store an agreed meeting point and time with a time zone. A hash-selected room
does not establish an accessible or agreed meeting location.

## Make the graph useful

Use visibly different relationships for community membership, suggestions,
accepted plans, and confirmed meetings. Joining a community must not imply
friendship, a mutual invitation, or physical attendance.

The graph should answer:

- Who am I arriving with, and what have we agreed to do?
- Who could introduce me to someone relevant to my ask or offer?
- Which conversations could my group join to meet people outside our community?
- If someone cancels, do I still have an arrival plan?

When plans change, offer an alternative introduction or a willing host welcome.
Do not silently enroll someone in another group or message other people without
their agreement. Keep requests for help private. Offer communities opportunities
to welcome newcomers, rather than only reinforcing existing circles.

## Accessibility and inclusion are acceptance criteria

- Offer text-first introductions, one-to-one or small-group participation, quiet
  or seated meeting preferences, and the option to bring a friend or companion.
  Ask what helps someone participate; do not require a diagnosis.
- Publish organizer-confirmed venue information where available: meeting points,
  entrances, step-free access, seating, quiet spaces, captions, and an access
  contact. Show unknown information as unknown. Preferences do not guarantee that
  a venue can provide an accommodation.
- Make graph participation, affiliation visibility, and location sharing separate
  opt-in choices. Withdrawal must remove the corresponding public information.
  Never display a public loneliness, popularity, or no-show score.
- Provide the same useful actions through a structured list as through the graph.
  Support keyboard and screen-reader use, visible focus, readable contrast,
  sufficiently large controls, reduced motion, and pausable animations.
- Provide a normal link or short-code alternative to QR or NFC. Keep essential
  information readable on small screens and slow connections. Do not require a
  LinkedIn account, resume, or paid Hallway account to participate.
- Let people decline invitations, block or report unwanted contact, and leave a
  group. Avoid rewards that pressure people to disclose identity or attend when
  they cannot. Community participation is not a popularity competition.
- Test the actual journey with different access needs and communication
  preferences. Use WCAG 2.2 AA as the interface target; do not claim conformance
  from a checklist alone.

## Work with Luma

Luma owns event registration, ticket validity, approval, cancellation, and event
check-in. Hallway owns its opt-in community membership, asks and offers,
introductions, arrival plans, and personal goals.

For the first usable version, accept an organizer-supplied Luma event URL and
provide clear links between the event and its Hallway invitation pages. Identify
this as a link-based integration; do not imply verified registration or check-in.

For synchronized integration, confirm organizer access and Luma Plus, then use
the calendar-scoped API and registration/check-in webhooks. Associate records by
verified external IDs, verify webhook authenticity using Luma's documented
mechanism, and handle retries without duplicate memberships or messages. Keep
Luma credentials server-side. Review current authentication, payloads, and
permissions before implementation. Do not scrape guest lists or assume arbitrary
attendee access. Obtain permission before sending invitations or outreach.

Sources: [Luma integrations](https://help.luma.com/p/integrations),
[API access](https://help.luma.com/p/luma-api),
[webhooks](https://help.luma.com/p/webhooks).

## Personal goals and continuation

Offer a small goal board or agenda: find a collaborator, learn about a topic,
meet a community, or help someone with an offer. Attendees choose what matters
and mark their own progress. A scan does not automatically complete a goal.

Afterward, show accepted plans, confirmed meetings, and optional follow-up ideas.
Let people continue their group, choose a shared project, or find the next Luma
event together. Share LinkedIn or other contact details only when participants
choose to. Set an explicit retention and deletion policy before retaining
conversations across events.

## Build order and completion checks

Each row is a separate, reviewable PR. Roles are suggested workstreams, not
assignments to named agents. Read existing code before choosing final API shapes.

| Order | Workstream | Deliverable and completion check |
| --- | --- | --- |
| 1 | Product and web | Before-arrival landing page with Luma event link, personal asks/offers, and clear implemented/planned labels. A newcomer can complete registration without using the graph. |
| 2 | Community API and web | Organizer signup, controlled editing, community invitation page, explicit member acceptance, and multiple affiliations. An unaffiliated person can proceed too. |
| 3 | Group API and web | Suggested arrival groups, accept/decline/leave, and stored time and meeting point. Test consent, private fields, concurrent capacity enforcement, and companion preferences. |
| 4 | Graph and web | Explainable introductions and private invitations; accepted plans and confirmed meetings stay distinct. Keyboard/list users can complete the same actions. |
| 5 | Luma integration | With confirmed access, synchronize registration and check-in updates. Replay an event without duplicate effects and verify cancellation changes the correct record. |
| 6 | Group API and web | Cancellation recovery with an offered replacement or willing host. Nobody changes groups or sends outreach without agreement. |
| 7 | Product and observability | Goal board, recap, and aggregate RSVP-to-plan-to-attendance view. Label simulated data and unknown attendance explicitly. |
| Later | Community continuity | Continued group conversations, next-event plans, and community bridges, with retention and moderation behavior defined. |

The minimum demo is a community invitation, asks/offers, an accepted arrival
group and meeting plan, a new connection during the event, and an after-event
next step. Show Luma check-in only when a real integration has been verified;
otherwise clearly label the external step or simulated event.

## Tooling and delivery

Keep Elasticsearch as the datastore and matching engine. Reuse the existing
hybrid search and add explicit mappings as needed. An Elastic agent proposing
connections is optional; it cannot accept connections on a person's behalf.
Use non-destructive schema changes or a tested migration. Do not delete shared
attendee indices to enable a feature. Disposable synthetic demos use isolated
index prefixes.

Use Dash0/OpenTelemetry for technical performance and aggregate product progress.
Keep sensitive affiliations, access preferences, free text, and attendee IDs out
of metric labels. Radar remains the deployment/investigation target. Our delivery
handoff is the GitHub repository; direct cluster access is not assumed.

Every feature and fix goes through a PR to `main`, Gitar review, and required
checks. Enable per-PR auto-apply and review the resulting changes. Keep schemas,
generated browser types, and API documentation aligned. Record real sponsor-tool
evidence and distinguish it from planned demonstrations.

The repository is the durable coordination record. Link each PR to its workstream,
state its implementation status, and note any contract changes or dependencies.
Use AgentSwarm for updates when reachable; do not depend on it as the only record.

## Measurement and open choices

Measure accepted arrival plans, organizer-confirmed check-ins, cancellations,
voluntary welcome/usefulness feedback, and continued participation. Report
cancellations separately from unobserved attendance. Do not infer no-shows from
missing Hallway activity or claim that self-selected group joiners prove impact.
Test the attendance hypothesis through an appropriate pilot comparison.

Still open: QR versus NFC; whether points/rewards belong at all; group size
defaults; communication channel and moderation; organizer verification; actual
Luma access; venue accommodation information; and retention duration. Optional
resume uploads, LinkedIn imports, navigation arrows, session recommendations,
and contests stay behind the complete arrival journey.

Accessibility references: [W3C event guidance](https://www.w3.org/WAI/teach-advocate/accessible-presentations/),
[WCAG 2.2](https://www.w3.org/TR/WCAG22/).
