import { Server as HTTPServer } from "http";
import { Rooms } from "./rooms";

// CORS headers for cross-origin requests
const CORS_HEADERS = {
	"Access-Control-Allow-Origin": "*",
	"Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
	"Access-Control-Allow-Headers": "Content-Type, Authorization",
};

// Type definitions for API responses
interface APIResponse {
	success?: boolean;
	error?: string;
	message?: string;
	roomid?: string;
	originalRoomid?: string;
	clonedAt?: string;
	turn?: number;
}

interface CloneResponse extends APIResponse {
	originalBattle: {
		roomid: string,
		title: string,
		format: string,
		turn: number,
		players: string[],
	};
	clonedBattle: {
		roomid: string,
		title: string,
		format: string,
		turn: number,
		players: string[],
	};
	directUrl?: string;
}

/**
 * Pokemon Showdown Battle Clone API
 * Provides endpoints to clone running battles for testing and analysis
 */
export class SimulatorCloneAPI {
	private server: HTTPServer;
	private port: number;
	private cloneCounter = 1;

	constructor(port = 3002) {
		this.port = port;
		this.server = new HTTPServer((req, res) => {
			void this.handleRequest(req, res);
		});
	}

	start() {
		this.server.listen(this.port, () => {
			console.log(`Battle Clone API server listening on port ${this.port}`);
			console.log(`Available endpoints:`);
			console.log(`  GET  /battles - List all active battles`);
			console.log(`  POST /battle/{id}/clone - Clone a specific battle`);
			console.log(`  GET  /clones - List all cloned battles`);
		});
	}

	stop() {
		this.server.close();
	}

	private handleRequest(req: any, res: any) {
		// Handle CORS preflight
		if (req.method === "OPTIONS") {
			res.writeHead(200, CORS_HEADERS);
			res.end();
			return;
		}

		const url = new URL(req.url, `http://localhost:${this.port}`);
		const pathParts = url.pathname.split("/").filter(Boolean);

		try {
			if (pathParts.length === 1 && pathParts[0] === "battles") {
				// GET /battles - List all active battles (for reference)
				this.handleGetBattles(res);
			} else if (pathParts.length === 1 && pathParts[0] === "clones") {
				// GET /clones - List all cloned battles
				this.handleGetClones(res);
			} else if (
				pathParts.length === 3 &&
				pathParts[0] === "battle" &&
				pathParts[2] === "clone" &&
				req.method === "POST"
			) {
				// POST /battle/{id}/clone - Clone a specific battle
				this.handleCloneBattle(pathParts[1], req, res);
			} else if (
				pathParts.length === 3 &&
				pathParts[0] === "battle" &&
				pathParts[2] === "info" &&
				req.method === "GET"
			) {
				// GET /battle/{id}/info - Get info about a cloned battle and how to join
				this.handleBattleInfo(pathParts[1], res);
			} else {
				this.handleNotFound(res);
			}
		} catch (error: any) {
			this.handleError(res, error);
		}
	}

	private handleGetBattles(res: any) {
		const battles = [];

		for (const room of Rooms.rooms.values()) {
			if (room.battle && !room.battle.ended) {
				battles.push({
					roomid: room.roomid,
					title: room.title,
					format: room.battle.format || "unknown",
					turn: room.battle.turn || 0,
					started: room.battle.started || false,
					ended: room.battle.ended || false,
					players: room.battle.players.map(p => p.name).filter(Boolean),
					isClone: room.roomid.includes("clone"),
				});
			}
		}

		res.writeHead(200, {
			"Content-Type": "application/json",
			...CORS_HEADERS,
		});
		res.end(
			JSON.stringify({
				success: true,
				battles,
				count: battles.length,
			})
		);
	}

	private handleGetClones(res: any) {
		const clones = [];

		for (const room of Rooms.rooms.values()) {
			if (room.battle && room.roomid.includes("clone")) {
				clones.push({
					roomid: room.roomid,
					title: room.title,
					format: room.battle.format || "unknown",
					turn: room.battle.turn || 0,
					started: room.battle.started || false,
					ended: room.battle.ended || false,
					players: room.battle.players.map(p => p.name).filter(Boolean),
					originalRoomid: room.roomid.split("-clone-")[0],
					clonedAt: (room as any).createdAt || new Date().toISOString(),
				});
			}
		}

		res.writeHead(200, {
			"Content-Type": "application/json",
			...CORS_HEADERS,
		});
		res.end(
			JSON.stringify({
				success: true,
				clones,
				count: clones.length,
			})
		);
	}

	private handleCloneBattle(battleId: string, req: any, res: any) {
		// Collect request data to get custom player2 parameter
		this.collectRequestData(req, requestData => {
			try {
				// Find the original battle
				const originalRoom = Rooms.get(battleId);
				if (!originalRoom?.battle) {
					res.writeHead(404, {
						"Content-Type": "application/json",
						...CORS_HEADERS,
					});
					res.end(
						JSON.stringify({
							success: false,
							error: "Battle not found",
							roomid: battleId,
						} as APIResponse)
					);
					return;
				}

				const originalBattle = originalRoom.battle;
				const customPlayer2 = requestData.player2; // Get player2 from request body

				// Check if battle is in a valid state for cloning
				if (originalBattle.ended) {
					res.writeHead(400, {
						"Content-Type": "application/json",
						...CORS_HEADERS,
					});
					res.end(
						JSON.stringify({
							success: false,
							error: "Cannot clone ended battle",
							roomid: battleId,
						} as APIResponse)
					);
					return;
				}

				// Generate unique clone room ID
				const cloneId = `${battleId}-clone-${this.cloneCounter++}`;

				// Use the input log approach for cloning
				console.log(
					`Cloning battle ${battleId} at turn ${originalBattle.turn}${
						customPlayer2 ? ` with custom player2: ${customPlayer2}` : ""
					}`
				);

				// Get the input log from the original battle for cloning
				originalBattle
					.getLog()
					.then(inputLog => {
						if (!inputLog || inputLog.length === 0) {
							res.writeHead(400, {
								"Content-Type": "application/json",
								...CORS_HEADERS,
							});
							res.end(
								JSON.stringify({
									success: false,
									error: "Could not retrieve battle log for cloning",
									roomid: battleId,
								} as APIResponse)
							);
							return;
						}

						// Modify input log to replace player2 if specified
						let modifiedInputLog = inputLog;
						if (customPlayer2) {
							const originalPlayer2 = originalBattle.players[1]?.name;
							if (originalPlayer2) {
								modifiedInputLog = inputLog.map(line =>
									line.replace(
										new RegExp(`\\b${originalPlayer2}\\b`, "g"),
										customPlayer2
									)
								);
								console.log(
									`Replaced player2 ${originalPlayer2} with ${customPlayer2} in input log`
								);
							}
						}

						// Create clone room with the same format using modified input log
						const cloneRoom = Rooms.createBattle({
							roomid: cloneId as RoomID,
							format: originalBattle.format,
							inputLog: modifiedInputLog.join("\n"),
							rated: false, // Clones are never rated
							players: [], // Empty array since players come from inputLog
						});

						if (!cloneRoom?.battle) {
							res.writeHead(500, {
								"Content-Type": "application/json",
								...CORS_HEADERS,
							});
							res.end(
								JSON.stringify({
									success: false,
									error: "Failed to create clone room",
									roomid: battleId,
								} as APIResponse)
							);
							return;
						}

						// Configure the cloned battle to be joinable by new players
						// Clear existing user connections so new players can join
						const clonedBattle = cloneRoom.battle;
						for (let i = 0; i < clonedBattle.players.length; i++) {
							const player = clonedBattle.players[i];
							// Use setPlayerUser to properly clear the user connection
							// This sets player.id to empty string and removes user references
							clonedBattle.setPlayerUser(player, null);

							// Change player names to indicate these are open slots
							// This prevents original players from being auto-redirected
							player.name = `slot${i + 1}`;
							player.invite = `slot${i + 1}` as ID;
						}

						// Make sure the battle room is joinable
						cloneRoom.settings.modjoin = null; // Allow anyone to join
						cloneRoom.settings.isPrivate = false; // Make it public

						// Add a message indicating this is a cloned battle that can be joined
						cloneRoom.add(
							'|raw|<div class="broadcast-blue"><strong>This is a cloned battle!</strong><br />New players can join with <code>/joingame p1</code> or <code>/joingame p2</code> to take control and continue the battle.<br />Player slots are currently: <strong>[Open Slot 1]</strong> vs <strong>[Open Slot 2]</strong></div>'
						); // Mark the room as created with timestamp
						(cloneRoom as any).createdAt = new Date().toISOString();

						// Prepare response data
						const response: CloneResponse = {
							success: true,
							message: "Battle cloned successfully",
							originalRoomid: battleId,
							roomid: cloneId,
							clonedAt: new Date().toISOString(),
							turn: cloneRoom.battle.turn,
							directUrl: `http://localhost:8000/${cloneId}`,
							originalBattle: {
								roomid: battleId,
								title: originalRoom.title,
								format: originalBattle.format,
								turn: originalBattle.turn,
								players: originalBattle.players.map(p => p.name),
							},
							clonedBattle: {
								roomid: cloneId,
								title: cloneRoom.title,
								format: cloneRoom.battle.format,
								turn: cloneRoom.battle.turn,
								players: cloneRoom.battle.players.map(p => p.name),
							},
						};

						console.log(
							`Successfully cloned battle ${battleId} -> ${cloneId}`
						);

						res.writeHead(200, {
							"Content-Type": "application/json",
							...CORS_HEADERS,
						});
						res.end(JSON.stringify(response));
					})
					.catch(error => {
						console.error(
							`Error getting log for battle ${battleId}:`,
							error
						);

						res.writeHead(500, {
							"Content-Type": "application/json",
							...CORS_HEADERS,
						});
						res.end(
							JSON.stringify({
								success: false,
								error: `Failed to get battle log: ${error.message}`,
								roomid: battleId,
							} as APIResponse)
						);
					});
			} catch (error: any) {
				console.error(`Error cloning battle ${battleId}:`, error);

				res.writeHead(500, {
					"Content-Type": "application/json",
					...CORS_HEADERS,
				});
				res.end(
					JSON.stringify({
						success: false,
						error: `Failed to clone battle: ${error.message}`,
						roomid: battleId,
					} as APIResponse)
				);
			}
		});
	}

	private handleNotFound(res: any) {
		res.writeHead(404, {
			"Content-Type": "application/json",
			...CORS_HEADERS,
		});
		res.end(
			JSON.stringify({
				success: false,
				error: "Endpoint not found",
				availableEndpoints: [
					"GET /battles - List all active battles",
					"POST /battle/{id}/clone - Clone a specific battle",
					"GET /clones - List all cloned battles",
				],
			})
		);
	}

	private handleBattleInfo(battleId: string, res: any) {
		try {
			const room = Rooms.get(battleId);
			if (!room?.battle) {
				res.writeHead(404, {
					"Content-Type": "application/json",
					...CORS_HEADERS,
				});
				res.end(
					JSON.stringify({
						success: false,
						error: "Battle not found",
						roomid: battleId,
					} as APIResponse)
				);
				return;
			}

			const battle = room.battle;
			const isClone = battleId.includes("-clone-");

			// Check which player slots are available for joining
			const joinableSlots = [];
			for (const player of battle.players) {
				if (!player.id) { // No user connected to this slot
					joinableSlots.push({
						slot: player.slot,
						name: player.name,
						hasTeam: player.hasTeam,
						active: player.active,
					});
				}
			}

			const response = {
				success: true,
				battle: {
					roomid: battleId,
					title: room.title,
					format: battle.format,
					turn: battle.turn,
					started: battle.started,
					ended: battle.ended,
					isClone,
					players: battle.players.map(p => ({
						slot: p.slot,
						name: p.name,
						connected: !!p.id,
						active: p.active,
						hasTeam: p.hasTeam,
					})),
					joinableSlots,
				},
				joinInstructions: isClone ? {
					message: "This is a cloned battle. You can join and take control!",
					commands: joinableSlots.map(slot => `/joingame ${slot.slot}`),
					directUrl: `http://localhost:8000/${battleId}`,
				} : {
					message: "This is an original battle. Players must be invited to join.",
					commands: [],
					directUrl: `http://localhost:8000/${battleId}`,
				},
			};

			res.writeHead(200, {
				"Content-Type": "application/json",
				...CORS_HEADERS,
			});
			res.end(JSON.stringify(response));
		} catch (error) {
			this.handleError(res, error instanceof Error ? error : new Error(String(error)));
		}
	}

	private handleError(res: any, error: Error) {
		console.error("API Error:", error);

		res.writeHead(500, {
			"Content-Type": "application/json",
			...CORS_HEADERS,
		});
		res.end(
			JSON.stringify({
				success: false,
				error: error.message || "Internal server error",
			} as APIResponse)
		);
	}

	/**
	 * Helper method to collect request data from POST requests
	 */
	private collectRequestData(req: any, callback: (data: any) => void) {
		let body = "";
		req.on("data", (chunk: string) => {
			body += chunk.toString();
		});
		req.on("end", () => {
			try {
				const data = body ? JSON.parse(body) : {};
				callback(data);
			} catch {
				throw new Error("Invalid JSON in request body");
			}
		});
	}
}
