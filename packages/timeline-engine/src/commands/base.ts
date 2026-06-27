import type { TimelineDocument } from "@montage/shared-types";

export interface TimelineCommand {
  readonly type: string;
  readonly description: string;
  apply(doc: TimelineDocument): TimelineDocument;
}

export abstract class BaseCommand implements TimelineCommand {
  abstract readonly type: string;
  abstract readonly description: string;
  abstract apply(doc: TimelineDocument): TimelineDocument;
}

export class BatchCommand extends BaseCommand {
  readonly type = "batch";
  readonly description: string;

  constructor(
    private readonly commands: TimelineCommand[],
    description = "Batch edit",
  ) {
    super();
    this.description = description;
  }

  apply(doc: TimelineDocument): TimelineDocument {
    return this.commands.reduce((current, command) => command.apply(current), doc);
  }

  getCommands(): TimelineCommand[] {
    return [...this.commands];
  }
}

export function serializeCommand(command: TimelineCommand): Record<string, unknown> {
  if (command instanceof BatchCommand) {
    return {
      type: "batch",
      description: command.description,
      commands: command.getCommands().map(serializeCommand),
    };
  }
  return {
    type: command.type,
    description: command.description,
    ...(command as unknown as Record<string, unknown>),
  };
}
