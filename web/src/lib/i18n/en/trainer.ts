import type { Dict } from "..";
import { enPlural } from "../plural";

const positions = (n: number) => `${n} ${enPlural(n, "position", "positions")}`;

const waitText = (seconds: number) => {
  if (seconds < 60) return `${seconds} s`;
  if (seconds < 3600) return `${Math.ceil(seconds / 60)} min`;
  return `${Math.ceil(seconds / 3600)} h`;
};

export const trainer: Dict["trainer"] = {
  title: "Opening trainer",
  heading: "Play your line",
  allCourses: "All courses",
  filter: "Course",
  counts: (due: number, fresh: number, learned: number, total: number) =>
    `${due} due · ${fresh} new · ${learned} of ${total} learned`,
  loading: "Loading position…",
  loadError: "Couldn't load the position",
  checkError: "Couldn't check the move",
  retry: "Retry",
  banner: { white: "White to move", black: "Black to move", main: "Course move!", alternative: "Also a good move", wrong: "Not the move" },
  status: {
    intro: "Your opponent is moving…",
    task: "Find the move of your line.",
    repeat: " You've seen this position before.",
    fresh: " A new course position.",
    checking: "Checking your move…",
    main: "Correct — that's the course move.",
    withHint: "With a hint the position comes back sooner.",
    alternative: (loss: string) => `The engine rates it as good as the course move${loss}. Counted, but the box doesn't grow.`,
    lossSuffix: (loss: number) => ` (${loss.toFixed(1)}% win chance lost)`,
    courseMove: "Course move:",
    wrong: (loss: string) => `This move is clearly worse${loss}.`,
    wrongLoss: (loss: number) => ` — ${loss.toFixed(1)}% win chance lost`,
    showAgain: (when: string) => `See you again ${when}.`,
    returns: (when: string) => `The position comes back ${when}.`,
  },
  box: (box: number, max: number) => `Box ${box} of ${max}`,
  boxLabel: "Review",
  learned: "Learned",
  hint: "Hint",
  hintShown: "Hint: the piece is highlighted",
  next: "Next position",
  nextLoading: "Loading…",
  openCourse: "Open in course",
  replay: "Show the course move",
  ideasTitle: "Remember the position ideas",
  session: (right: number, wrong: number) => `This session: ${right} correct, ${wrong} mistakes`,
  empty: {
    title: "Nothing to train yet",
    text: "Create a course for an opening and train your side: positions you get wrong come back more often.",
    link: "To the course catalog",
  },
  done: {
    title: "All done for today!",
    text: (learned: number, total: number) =>
      `New positions are done, reviews will show up later. ${positions(learned)} of ${total} learned.`,
    course: "To the course",
    all: "All courses",
  },
  notReady: "The course is still being built — training opens once it's ready.",
  errors: {
    rateLimited: (seconds: number) => `Too many answers in a row. Take a ${waitText(seconds)} break.`,
    courseLimited: (seconds: number) => `Too many new courses. Try again in ${waitText(seconds)}.`,
    engine: "The engine couldn't check the move — try again.",
  },
  sound: { on: "Turn sound on", off: "Turn sound off" },
};
