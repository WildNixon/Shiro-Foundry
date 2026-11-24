# This project's rules and lessons

Read the section for the situation you are in. Each line is a rule the project paid for; say in a few words what taught it. The founder writes the first version with the user; after that a line is added the way any change to how the crew works is: logged in the journal, planned by the manager, approved by the user.

Keep it short. A rule that holds in every project belongs in the skills, not here.

## Always

- (Whether the crew may push, and where.)
- (What needs the user's word every time: heavy work on a shared machine, anything outside the repository, spending.)
- (Where captures, logs and scratch files go, and that the folder is git-ignored.)

## The host

- (The interpreter to use and why. Example: "Run Python by its full path; the bare alias on this machine starts a different one.")
- (What the shell here cannot do. Example: "Never feed python on stdin: it hangs. Write a script file and run it.")
- (What is not installed on the host and where it runs instead.)

## At a slot start

- (What the manager checks before any work: the machine, the shared resource, what the last slot left running.)
- (Where the plan's weekly usage is read, and what happens at the stop.)

## Using the shared resource

- (What it is, how many seats, what a job may assume about a seat.)
- (What is cleaned between jobs and by whom.)
- (How it is brought back up after a restart, and how to tell a real restart from a resume.)
- (How a stuck job is stopped, in what order, and that each kill needs its own yes from the user.)

## Merging

- (The merge gate: the checks run on the merged tree before the next block builds on it.)
- (The full check at each slot's end, and the command of a sweep if the project has one.)

## The charts

- (Any reader of this project's own that draws a system graph, and who may run it.)

## Before a counted run

- (A dev run, dry-graded by the grader, first.)
- (What must be green and clean; who may commit to the main branch while it runs: nobody.)

## Before a builder hands in

- (The checks every change runs: format, lint, tests.)
- (The extra check for a change to shipped code.)

## Shared files

- (Files every lane reads, so a change there moves other lanes.)

## Reporting

- (Run results go to the contract owner's amendment, not to shared notes a grader reads before pinning.)

## Closing a push

- (The freeze, the full sweep, where the close note goes.)
