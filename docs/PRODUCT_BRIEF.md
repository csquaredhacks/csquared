# Hallway product brief

**Meet your group before the conference. Arrive with familiar people. Grow those
connections during the event and keep them afterward.**

This brief records the team's product direction from Matt's idea board on
November 9, 2026. It replaces the older decision to defer pre-conference features.
It describes the intended experience, not a claim that every flow is implemented.
[API.md](API.md) describes the current API contract.

## The problem

Conferences can feel overwhelming when you arrive alone, have a specific goal,
or find it difficult to approach a room of strangers. Hallway helps people build
familiarity before arrival and gives them a group to participate with throughout
the event. The connection graph helps that group keep growing.

## Before the conference: find your group

- Encourage attendees to register early so they have time to meet beforehand.
- Let organizers create community groups, share invitations, and encourage members
  to invite their friends and communities. Early introductions build anticipation
  for both attendees and organizers.
- Let attendees choose communities they belong to or want to participate in,
  such as Girls Who Code, Latinos Who Code, a university, or a local meetup.
  Shared membership helps people find one another. Membership is self-selected.
- Collect what each attendee is working on, a list of **asks**, and a list of
  **offers**. Examples include learning about startups, sharing industry knowledge,
  finding a founding partner, or getting help with a technical problem.
- Recommend five relevant people with concrete explanations based on those asks
  and offers, interests, and chosen groups.
- Help attendees form or join an initial group and start an icebreaker conversation
  before arrival. They can also invite people they already know.
- Give the group a way to agree on an initial meeting place and plan. Match
  recommendations alone do not complete this experience.
- Offer a personal goal board or agenda so attendees can remember why they came
  and choose activities that help them make progress.

An organizer's community group and an attendee's initial group are different.
A community can contain many attendees; an initial group is the set of people
someone plans to arrive and participate with. Shared membership does not itself
mean two people have met or accepted a personal connection.

## During the conference: stay connected and expand

- Show the initial graph of participating groups, familiar people, and accepted
  connections when the conference starts.
- Keep the initial group accessible as attendees explore. People can attend
  sessions together, reconnect during breaks, or introduce a friend to someone new.
- Continue suggesting the top three relevant people, groups, or conversations as
  asks, offers, and connections change. Include useful connection chains so a
  familiar person can help make an introduction.
- Let attendees discover and join growing conversations that interest them.
- Let people confirm new connections throughout the day. The graph reflects
  accepted connections and distinguishes them from suggested introductions.
- Offer a separate opt-in room or crowd map for finding participating connections
  and group members. Connection sharing and location sharing are separate choices.
- Keep goals and the personal agenda available while the event is busy.

Elasticsearch should support the matching and graph experience: combine asks and
offers with search, suggest relevant connections, and refresh those suggestions
as the event evolves. An Elastic agent that proposes connections is an option
to investigate, not a settled requirement. Suggested edges must remain distinct
from connections attendees have actually accepted.

## After the conference: continue the relationships

- Give attendees a recap of people they met, conversations they joined, and
  progress toward the goals they chose.
- Keep the initial group and new conversations available for people who want to
  stay in touch, with a clear next action such as another meetup or shared project.
- Offer follow-up prompts and optional LinkedIn connection suggestions in the
  conversations where participants choose to share those details.

## Inclusion and accessibility

People can bring existing friends, find a new group, or participate one-to-one.
The experience must support different comfort levels rather than require a single
way to socialize. Offer clear meeting arrangements and optional preferences such
as text-first introductions, small groups, quiet spaces, or seated meetups.

Ask attendees whether they want to appear on a connection graph. Participation
must be opt-in, with a way to withdraw. People choose which community memberships
and contact details they share. Neither a hidden profile nor a small number of
connections should publicly label someone as isolated.

Accessibility also applies to the interface: labelled controls, visible keyboard
focus, readable contrast, and a usable list alternative to the visual graph.

## Build priorities

The first complete demonstration should show an attendee register before the
event, use asks and offers to find an initial group, make an arrival plan, add a
new connection during the event, and choose a way to continue afterward.

Build that journey before adding rewards, contact imports, or navigation arrows.
Use real observed behavior when describing what works. A scan alone is not proof
of a useful conversation or a lasting friendship.

## Ideas and decisions still open

- **QR or NFC:** not settled. The existing QR implementation does not decide the
  final interaction. Compare attendee convenience and available hardware.
- **Points and rewards:** not settled. Ideas include attending activities with a
  group or recognizing community participation. Decide what points mean and how
  they are used before building an economy or a best-represented-group contest.
- **Group formation:** decide group sizes, how people accept a suggested group,
  and how they can invite friends, switch groups, or leave.
- **Outreach and conversations:** choose how recommendations, invitations, group
  icebreakers, and post-event conversations are delivered and retained.
- **Optional profile enrichment:** an interesting fact, resume upload, LinkedIn
  connection, or private lookup of people already known by name or email. These
  are ideas to evaluate, not requirements for joining.
- **Finder and directions:** room or person navigation arrows are a possible
  extension once the underlying opt-in location experience is useful.

## Demo story

1. Before: an attendee joins a chosen community, enters an ask and an offer, meets
   an initial group, and agrees where to meet them.
2. During: the attendee arrives with familiar people. A relevant introduction
   expands the group, and the graph shows the new accepted connection.
3. After: the attendee sees a recap and makes a next plan with that group.

The promise is that nobody needs to start alone, and their connections can keep
growing beyond the event.
