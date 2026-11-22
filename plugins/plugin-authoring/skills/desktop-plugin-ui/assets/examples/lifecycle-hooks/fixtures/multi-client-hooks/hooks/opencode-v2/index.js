import recorder from "../record.cjs";

export default {
  id: "multi-client-hooks",
  setup(context) {
    const controller = new AbortController();
    const created = context.event.subscribe({
      types: ["session.created"],
      signal: controller.signal,
    });

    async function recordSessions() {
      for await (const event of created) {
        if (event.type === "session.created") {
          recorder.record("opencode-v2:session.created");
        }
      }
    }

    void recordSessions().catch((error) => {
      if (!controller.signal.aborted) {
        console.error(error);
      }
    });

    return () => controller.abort();
  },
};
